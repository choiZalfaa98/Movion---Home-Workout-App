import torch
import torch.nn as nn
import numpy as np
from collections import deque, Counter
from pathlib import Path

# LABEL MAPPING HERE IS THE SAME AS THE ONE WHEN TRAINING THE LSTM MODEL
LABEL_MAP = {
    0: "jumping_jacks",
    1: "squat",
    2: "mountain_climber",
    3: "knee_push_up",
    4: "sit_up",
}

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# MODEL ARCHITECTURE WHICH IS THE SAME WHEN TRAINING THE LSTM MODEL
class SpatialTemporalAttentionLSTM(nn.Module):
    def __init__(self, input_size=217, hidden_size=128, num_classes=5):
        super().__init__()

        self.spatial_attn = nn.Linear(input_size, input_size)

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            dropout=0.3
        )

        self.norm = nn.LayerNorm(hidden_size)

        self.temporal_attn = nn.Linear(hidden_size, 1)

        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, 128),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(128, num_classes)
        )

    def forward(self, x, lengths_cpu, lengths_gpu):
        mask = torch.arange(x.size(1), device=x.device)[None, :] < lengths_gpu[:, None]

        spatial_weights = torch.softmax(self.spatial_attn(x), dim=-1)
        x = x * spatial_weights
        x = x * mask.unsqueeze(-1).float()

        packed = nn.utils.rnn.pack_padded_sequence(
            x, lengths_cpu, batch_first=True, enforce_sorted=False  # CPU
        )
        lstm_out, _ = self.lstm(packed)
        lstm_out, _ = nn.utils.rnn.pad_packed_sequence(
            lstm_out, batch_first=True, total_length=x.size(1)
        )
        lstm_out = self.norm(lstm_out)

        attn_scores = self.temporal_attn(lstm_out).squeeze(-1)
        attn_scores = attn_scores.masked_fill(~mask, float('-inf'))
        temporal_weights = torch.softmax(attn_scores, dim=1)

        context = torch.sum(lstm_out * temporal_weights.unsqueeze(-1), dim=1)
        return self.classifier(context)


class AttnLSTMClassifier:
    """
    Real-time movement-context classifier
    Sliding window buffer + majority voting (when inference across frames) for movement classification in real-time.

    Flow:
    - each frame push features to buffer (120 frames)
    - each N frame (inference_interval) will do the LSTM inference
    - from M last inference results will do majority voting
    - if votes >= voting_threshold, it'll result to the final labeling of classification

    Low confidence inferences are inserted into the vote window as UNKNOWN
    """

    INPUT_SIZE = 217
    SEQUENCE_LENGTH   = 120
    MIN_FRAMES_FOR_INFER = 24
    INFERENCE_INTERVAL = 2
    VOTE_WINDOW       = 3
    VOTE_THRESHOLD    = 0.66
    CONF_THRESHOLD     = 0.75

    def __init__(self, model_path: str | None = None):
        if model_path is None:
            model_path = str(BASE_DIR / "models" / "best_attn_lstm_model.pth")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[LSTM] Running on: {self.device}")

        self.model = SpatialTemporalAttentionLSTM().to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()
        print(f"[LSTM] Model loaded: {model_path}")

        self._buffer = deque(maxlen=self.SEQUENCE_LENGTH)
        self._frame_count = 0
        self._vote_history: deque[tuple[str | None, float]] = deque(
            maxlen=self.VOTE_WINDOW
        )

        self.last_label: str | None = None
        self.last_confidence = 0.0
        self.last_voted: str | None = None
        self.last_voted_confidence = 0.0

    def push(self, features: np.ndarray) -> dict | None:
        """
        Insert 1 features frame (217,) to buffer.
        Return classification result when inference running, else None.

        Return dict:
          {
            "label":      str   — raw label from this inference
            "confidence": float — confidence of this inference
            "voted":      str | None — label final after majority voting (None if votes not enough)
          }
        """
        feature_array = np.asarray(features, dtype=np.float32).reshape(-1)
        if feature_array.shape != (self.INPUT_SIZE,):
            raise ValueError(
                f"Expected feature shape ({self.INPUT_SIZE},), "
                f"got {feature_array.shape}"
            )
        if not np.isfinite(feature_array).all():
            raise ValueError("LSTM features contain NaN or infinite values")

        self._buffer.append(feature_array)
        self._frame_count += 1

        if len(self._buffer) < self.MIN_FRAMES_FOR_INFER:
            return None
        if self._frame_count % self.INFERENCE_INTERVAL != 0:
            return None

        return self._infer()

    def reset(self): # reset buffer and vote history
        self._buffer.clear()
        self._vote_history.clear()
        self._frame_count = 0
        self.last_label = None
        self.last_confidence = 0.0
        self.last_voted = None
        self.last_voted_confidence = 0.0
        print("[LSTM] Buffer reset")

    def _infer(self) -> dict:
        actual_len = len(self._buffer)
        seq = np.asarray(self._buffer, dtype=np.float32)

        if actual_len < self.SEQUENCE_LENGTH:
            pad = np.zeros(
                (self.SEQUENCE_LENGTH - actual_len, seq.shape[1]),
                dtype=np.float32,
            )
            seq = np.vstack([seq, pad])

        x = torch.from_numpy(seq).unsqueeze(0).to(self.device)
        lengths_cpu = torch.tensor([actual_len], dtype=torch.long)
        lengths_gpu = lengths_cpu.to(self.device)

        with torch.inference_mode():
            logits = self.model(x, lengths_cpu, lengths_gpu)
            probs = torch.softmax(logits, dim=-1)

        prob_np = probs[0].cpu().numpy()
        class_idx = int(np.argmax(prob_np))
        confidence = float(prob_np[class_idx])
        label = LABEL_MAP[class_idx] if confidence >= self.CONF_THRESHOLD else None

        self.last_label = label
        self.last_confidence = confidence

        # UNKNOWN must age out stale labels instead of leaving history unchanged.
        self._vote_history.append((label, confidence))
        voted, voted_confidence = self._majority_vote()
        self.last_voted = voted
        self.last_voted_confidence = voted_confidence

        return {
            "label": label,
            "confidence": confidence,
            "voted": voted,
            "voted_confidence": voted_confidence,
            "status": "KNOWN" if voted is not None else "UNKNOWN",
        }

    def _majority_vote(self) -> tuple[str | None, float]:
        if len(self._vote_history) < self.VOTE_WINDOW:
            return None, 0.0

        labels = [label for label, _ in self._vote_history]
        known_labels = [label for label in labels if label is not None]
        if not known_labels:
            return None, 0.0

        top_label, top_count = Counter(known_labels).most_common(1)[0]

        ratio = top_count / len(self._vote_history)
        if ratio < self.VOTE_THRESHOLD:
            return None, 0.0

        confidences = [
            confidence
            for label, confidence in self._vote_history
            if label == top_label
        ]
        voted_confidence = float(np.mean(confidences)) if confidences else 0.0
        return top_label, voted_confidence
