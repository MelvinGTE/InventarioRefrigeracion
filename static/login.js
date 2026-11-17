document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const togglePasswordBtn = document.getElementById('togglePassword');
    const eyeOpen = document.getElementById('eyeOpen');
    const eyeClosed = document.getElementById('eyeClosed');
    const submitBtn = document.getElementById('submitBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnSpinner = document.getElementById('btnSpinner');

    const usernameError = document.getElementById('usernameError');
    const passwordError = document.getElementById('passwordError');

    // 1. Alternar visibilidad de contraseña
    togglePasswordBtn.addEventListener('click', () => {
        const isPassword = passwordInput.type === 'password';
        passwordInput.type = isPassword ? 'text' : 'password';
        
        eyeOpen.classList.toggle('hidden', isPassword);
        eyeClosed.classList.toggle('hidden', !isPassword);
        togglePasswordBtn.setAttribute(
            'aria-label', 
            isPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'
        );
    });

    // 2. Limpiar estado de error mientras el usuario escribe
    const clearError = (input, errorElement) => {
        input.closest('.input-wrapper').classList.remove('has-error');
        errorElement.textContent = '';
    };

    usernameInput.addEventListener('input', () => clearError(usernameInput, usernameError));
    passwordInput.addEventListener('input', () => clearError(passwordInput, passwordError));

    // 3. Validación del lado del cliente y feedback visual al enviar
    loginForm.addEventListener('submit', (e) => {
        let isValid = true;

        if (!usernameInput.value.trim()) {
            usernameInput.closest('.input-wrapper').classList.add('has-error');
            usernameError.textContent = 'Ingresa tu usuario para continuar.';
            isValid = false;
        }

        if (!passwordInput.value.trim()) {
            passwordInput.closest('.input-wrapper').classList.add('has-error');
            passwordError.textContent = 'Ingresa tu contraseña.';
            isValid = false;
        }

        if (!isValid) {
            e.preventDefault();
            return;
        }

        // Activar estado de carga para evitar doble envío en móvil/PC
        submitBtn.disabled = true;
        btnText.textContent = 'Verificando...';
        btnSpinner.classList.remove('hidden');
    });
});