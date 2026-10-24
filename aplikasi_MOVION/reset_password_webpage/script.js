const supabaseUrl = "https://jnbqvacvpnyrykdqahtq.supabase.co";

const supabaseKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpuYnF2YWN2cG55cnlrZHFhaHRxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAwNjYwMDAsImV4cCI6MjA5NTY0MjAwMH0.fgcb4KsypHbsA5shMkjSryZ86vYVpOx_dLL99yAWdCk";

const client = supabase.createClient(supabaseUrl, supabaseKey, {
    auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true
    }
});

const resetForm = document.getElementById("resetForm");
const passwordInput = document.getElementById("password");
const confirmPasswordInput = document.getElementById("confirmPassword");
const resetBtn = document.getElementById("resetBtn");
const msg = document.getElementById("msg");

let recoverySessionReady = false;

function showMessage(text, type = "info") {
    msg.innerText = text;
    msg.className = `message ${type}`;
}

function setLoading(isLoading) {
    resetBtn.disabled = isLoading;
    resetBtn.innerText = isLoading ? "Updating Password..." : "Reset Password";
}

client.auth.onAuthStateChange((event, session) => {
    if (event === "PASSWORD_RECOVERY" && session) {
        recoverySessionReady = true;
        showMessage("Reset session detected. You can enter your new password.", "info");
    }

    if (event === "USER_UPDATED") {
        showMessage("Password changed successfully!", "success");
    }
});

async function checkSession() {
    const {
        data: { session },
        error
    } = await client.auth.getSession();

    if (error) {
        showMessage(error.message, "error");
        return;
    }

    if (session) {
        recoverySessionReady = true;
        showMessage("Enter your new password to continue.", "info");
    } else {
        showMessage("Open this page from the reset-password link in your email.", "info");
    }
}

checkSession();

resetForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const password = passwordInput.value.trim();
    const confirmPassword = confirmPasswordInput.value.trim();

    if (!password || !confirmPassword) {
        showMessage("Please fill in both password fields.", "error");
        return;
    }

    if (password.length < 8) {
        showMessage("Password must be at least 8 characters.", "error");
        return;
    }

    if (password !== confirmPassword) {
        showMessage("Passwords do not match.", "error");
        return;
    }

    if (!recoverySessionReady) {
        showMessage("Reset session is not ready. Please reopen the link from your email.", "error");
        return;
    }

    setLoading(true);

    const { error } = await client.auth.updateUser({
        password: password
    });

    setLoading(false);

    if (error) {
        showMessage(error.message, "error");
        return;
    }

    showMessage("Password changed successfully! You can now log in with your new password.", "success");

    passwordInput.value = "";
    confirmPasswordInput.value = "";
});