# Movion — AI-Powered Home Workout Application

Movion is a desktop application that helps users perform home workouts with real-time camera-based movement detection and exercise tracking. It uses pose estimation and a custom-trained Attention LSTM model to recognize workout movements and support workout session monitoring.

The project combines computer vision, deep learning, and desktop application development to provide an interactive home workout experience.

## Features

- **Real-Time Movement Detection** — Captures camera input and extracts human pose information during workouts.
- **AI-Based Exercise Recognition** — Uses a custom-trained Attention LSTM model to classify workout movements.
- **Multiple Workout Modes** — Supports single-person and two-person workout sessions.
- **Workout Tracking** — Tracks exercise activity, repetitions, and session duration.
- **Workout Reports** — Generates a report after each workout session.
- **User Authentication** — Provides account-related features integrated with Supabase.
- **Workout History and Dashboard** — Helps users review workout activity and session information.

## Tech Stack

- **Programming Language:** Python
- **Desktop UI:** PyQt6
- **Computer Vision:** OpenCV, MediaPipe, YOLO
- **Deep Learning:** PyTorch, Attention LSTM
- **Backend and Authentication:** Supabase
- **Configuration and Environment Management:** Conda

## Installation and Setup

### Prerequisites

- Anaconda or Miniconda
- Git
- A compatible webcam for real-time workout tracking

### 1. Clone the Repository

```bash
git clone https://github.com/choiZalfaa98/Movion---Home-Workout-App.git
cd Movion---Home-Workout-App
```

### 2. Create the Conda Environment

Create the environment using the provided configuration file:

```bash
conda env create -f environment.yml
```

Activate the environment using the name defined in `environment.yml`. For example, if the environment name is `homeWorkoutApp`:

```bash
conda activate homeWorkoutApp
```

If the environment already exists locally, activate it instead of creating it again.

### 3. Configure Environment Variables

The original `.env` file is not included in this repository. A template named `.env.example` is provided instead.

From the repository root, create a local `.env` file:

```powershell
Copy-Item aplikasi_MOVION/.env.example aplikasi_MOVION/.env
```

Open `aplikasi_MOVION/.env` and fill in the required values using your own configuration (hint: script.js).

Make sure the required Supabase URL and public client key are configured correctly.

### 4. Run the Application

From the repository root directory, run:

```bash
python aplikasi_MOVION/main.py
```

Make sure the Conda environment is activated before launching the application.

## Training Data and Model Files

The training datasets are **not included in this repository** because of their large storage requirements, which can reach multiple gigabytes.

The repository retains selected training notebooks and relevant project files, while large dataset directories are excluded to keep the repository manageable.

Consequently, reproducing the full model training process requires obtaining or preparing the corresponding datasets separately.

## Notes and Limitations

- Application functionality depends on correct environment configuration and the availability of required model files.
- Supabase-dependent features require a properly configured Supabase project.
- Camera-based workout tracking requires a working camera and a suitable environment for movement detection.
- The included model artifacts may be used by the application, but the training datasets are not bundled with this repository.

## Project Purpose

Movion was developed as a project exploring the integration of computer vision, deep learning, and desktop application development for home workout assistance.

The project demonstrates practical implementation of AI-based movement recognition, camera processing, workout session management, and user-facing application features.

---

**Developed as an academic software project.**