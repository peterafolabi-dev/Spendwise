/**
 * SpendWise — Legendary Financial Engine & Power Features
 * Includes:
 * 1. Global Command Palette (Cmd/Ctrl + K)
 * 2. One-Click Privacy Mode (Shift + P & Eye toggle)
 * 3. User-specific financial coach
 * 5. Bill Splitting & Shared Expense Calculator
 * 6. Receipt attachment entry point
 * 7. WebAuthn Biometric & Passkey Authenticator
 * 8. Confetti Celebration Engine
 * 9. Quick Add Transaction Drawer with Optimistic UI
 * 10. Audit Tax Report Generator
 */

(function () {
    'use strict';

    // ── 1. PRIVACY MODE ──────────────────────────────────────────────────────────
    const initPrivacyMode = () => {
        const isPrivate = localStorage.getItem('spendwise_privacy') === 'true';
        if (isPrivate) {
            document.body.classList.add('privacy-mode', 'privacy-active');
            document.documentElement.classList.add('privacy-mode', 'privacy-active');
        }
        updatePrivacyButton(isPrivate);

        window.togglePrivacyMode = function () {
            const active = document.body.classList.toggle('privacy-mode');
            document.body.classList.toggle('privacy-active', active);
            document.documentElement.classList.toggle('privacy-mode', active);
            document.documentElement.classList.toggle('privacy-active', active);
            localStorage.setItem('spendwise_privacy', active);
            updatePrivacyButton(active);
            if (active) {
                showToast('🔒 Privacy Mode Enabled — Balances blurred');
            } else {
                showToast('👁️ Privacy Mode Disabled');
            }
        };

        document.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'p') {
                e.preventDefault();
                window.togglePrivacyMode();
            }
        });
    };

    function updatePrivacyButton(active) {
        const btn = document.getElementById('privacy-toggle-btn');
        if (!btn) return;
        btn.innerHTML = active
            ? `<svg class="w-5 h-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/></svg>`
            : `<svg class="w-5 h-5 text-slate-500 dark:text-slate-400 hover:text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>`;
        btn.setAttribute('title', active ? 'Turn off Privacy Mode (Ctrl+P)' : 'Hide balances in public (Ctrl+P)');
    }

    // ── 2. GLOBAL COMMAND PALETTE (CMD+K / CTRL+K) ───────────────────────────────
    const commands = [
        { title: 'New Transaction', category: 'Actions', icon: '➕', action: () => openQuickAddModal() },
        { title: 'Ask AI Copilot', category: 'Intelligence', icon: '🤖', action: () => openCopilotModal() },
        { title: 'Split a Bill / Expenses', category: 'Tools', icon: '🧾', action: () => openBillSplitter() },
        { title: 'Receipt attachment information', category: 'Tools', icon: '📸', action: () => openReceiptScanner() },
        { title: 'Toggle Privacy Mode', category: 'Settings', icon: '👁️', action: () => window.togglePrivacyMode() },
        { title: 'Toggle Dark / Light Theme', category: 'Settings', icon: '🌓', action: () => document.getElementById('theme-toggle')?.click() },
        { title: 'Dashboard', category: 'Navigation', icon: '📊', url: '/dashboard/' },
        { title: 'Transactions Ledger', category: 'Navigation', icon: '💳', url: '/transactions/' },
        { title: 'Accounts & Wallets', category: 'Navigation', icon: '🏦', url: '/accounts/' },
        { title: 'Budgets & Limits', category: 'Navigation', icon: '🎯', url: '/budgets/' },
        { title: 'Savings Goals', category: 'Navigation', icon: '🏆', url: '/savings/' },
        { title: 'Recurring Subscriptions', category: 'Navigation', icon: '🔄', url: '/recurring/' },
        { title: 'Reports & Analytics', category: 'Navigation', icon: '📈', url: '/reports/' },
        { title: 'Export CSV / Tax Sheet', category: 'Actions', icon: '📥', url: '/export/csv/' },
        { title: 'Import Bank CSV', category: 'Actions', icon: '📤', url: '/import/csv/' },
        { title: 'Profile & Security', category: 'Navigation', icon: '⚙️', url: '/profile/' }
    ];

    let selectedCmdIndex = 0;
    let filteredCommands = [...commands];

    window.openCommandPalette = function () {
        const modal = document.getElementById('cmd-palette-modal');
        if (!modal) return;
        modal.classList.remove('hidden');
        const input = document.getElementById('cmd-palette-input');
        if (input) {
            input.value = '';
            input.focus();
            filterCommands('');
        }
    };

    window.closeCommandPalette = function () {
        const modal = document.getElementById('cmd-palette-modal');
        if (modal) modal.classList.add('hidden');
    };

    function filterCommands(query) {
        const q = query.toLowerCase().trim();
        filteredCommands = commands.filter(c => c.title.toLowerCase().includes(q) || c.category.toLowerCase().includes(q));
        selectedCmdIndex = 0;
        renderCommandList();
    }

    function renderCommandList() {
        const list = document.getElementById('cmd-palette-results');
        if (!list) return;
        if (filteredCommands.length === 0) {
            list.innerHTML = `<div class="p-6 text-center text-sm text-slate-500">No matching commands found.</div>`;
            return;
        }

        list.innerHTML = filteredCommands.map((cmd, idx) => `
            <div class="cmd-item flex items-center justify-between px-4 py-3 cursor-pointer rounded-xl text-sm transition-colors ${idx === selectedCmdIndex ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold' : 'text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60'}" data-index="${idx}">
                <div class="flex items-center gap-3">
                    <span class="text-xl">${cmd.icon}</span>
                    <span>${cmd.title}</span>
                </div>
                <span class="text-xs uppercase tracking-wider text-slate-400 font-medium px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800">${cmd.category}</span>
            </div>
        `).join('');

        list.querySelectorAll('.cmd-item').forEach(item => {
            item.addEventListener('click', () => {
                const idx = parseInt(item.getAttribute('data-index'), 10);
                executeCommand(filteredCommands[idx]);
            });
        });
    }

    function executeCommand(cmd) {
        if (!cmd) return;
        closeCommandPalette();
        if (cmd.url) {
            window.location.href = cmd.url;
        } else if (cmd.action) {
            cmd.action();
        }
    }

    const initCommandPalette = () => {
        document.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                const modal = document.getElementById('cmd-palette-modal');
                if (modal && !modal.classList.contains('hidden')) {
                    closeCommandPalette();
                } else {
                    openCommandPalette();
                }
            } else if (e.key === 'Escape') {
                closeCommandPalette();
                closeCopilotModal();
                closeBillSplitter();
                closeReceiptScanner();
            }
        });

        const input = document.getElementById('cmd-palette-input');
        if (input) {
            input.addEventListener('input', (e) => filterCommands(e.target.value));
            input.addEventListener('keydown', (e) => {
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    selectedCmdIndex = (selectedCmdIndex + 1) % filteredCommands.length;
                    renderCommandList();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    selectedCmdIndex = (selectedCmdIndex - 1 + filteredCommands.length) % filteredCommands.length;
                    renderCommandList();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    if (filteredCommands[selectedCmdIndex]) {
                        executeCommand(filteredCommands[selectedCmdIndex]);
                    }
                }
            });
        }
    };

    // ── 4. AI FINANCIAL COPILOT ──────────────────────────────────────────────────
    window.closeCopilotModal = function () {
        const modal = document.getElementById('copilot-modal');
        if (modal) modal.classList.add('hidden');
    };

    let copilotContextLoaded = false;

    window.openCopilotModal = function () {
        const modal = document.getElementById('copilot-modal');
        if (modal) modal.classList.remove('hidden');
        if (copilotContextLoaded) return;
        copilotContextLoaded = true;
        fetch('/api/copilot/context/')
            .then(async response => {
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || 'Could not load your snapshot.');
                const greeting = document.getElementById('copilot-greeting');
                if (greeting) greeting.textContent = result.greeting;
            })
            .catch(error => {
                console.error('Copilot context request failed:', error);
                const greeting = document.getElementById('copilot-greeting');
                if (greeting) greeting.textContent = 'Your spending snapshot could not be loaded. Try reopening the assistant.';
                copilotContextLoaded = false;
            });
    };

    window.sendCopilotQuery = async function (prefilledText) {
        const input = document.getElementById('copilot-input');
        const text = (prefilledText || (input ? input.value : '')).trim();
        const chatBox = document.getElementById('copilot-chat-messages');
        if (!text || !chatBox) return;

        const addMessage = (message, isUser) => {
            const row = document.createElement('div');
            row.className = isUser
                ? 'flex justify-end mb-3'
                : 'flex items-start gap-2.5 mb-4 animate-fade-in-up';
            if (!isUser) {
                const icon = document.createElement('div');
                icon.className = 'w-7 h-7 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm shrink-0';
                icon.textContent = '🤖';
                row.appendChild(icon);
            }
            const bubble = document.createElement('div');
            bubble.className = isUser
                ? 'bg-emerald-600 text-white rounded-2xl rounded-tr-none px-4 py-2 text-sm max-w-[80%] shadow-sm whitespace-pre-line'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-2xl rounded-tl-none px-4 py-3 text-sm max-w-[85%] shadow-sm border border-slate-200/50 dark:border-slate-700/50 leading-relaxed whitespace-pre-line';
            bubble.textContent = message;
            row.appendChild(bubble);
            chatBox.appendChild(row);
            chatBox.scrollTop = chatBox.scrollHeight;
            return bubble;
        };

        addMessage(text, true);
        if (input) input.value = '';
        const pending = addMessage('Checking your recorded figures…', false);
        try {
            const response = await fetch('/api/copilot/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({ message: text }),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || 'Could not answer that question.');
            pending.textContent = result.reply;
        } catch (error) {
            console.error('Copilot chat request failed:', error);
            pending.textContent = error.message || 'Could not reach the money coach. Please try again.';
            pending.classList.add('text-rose-500');
        }
        chatBox.scrollTop = chatBox.scrollHeight;
    };

    // ── 5. BILL SPLITTER & SHARED EXPENSES ───────────────────────────────────────
    window.openBillSplitter = function () {
        const modal = document.getElementById('bill-splitter-modal');
        if (modal) modal.classList.remove('hidden');
        recalculateBillSplit();
    };

    window.closeBillSplitter = function () {
        const modal = document.getElementById('bill-splitter-modal');
        if (modal) modal.classList.add('hidden');
    };

    window.recalculateBillSplit = function () {
        const total = parseFloat(document.getElementById('split-total-bill')?.value) || 0;
        const tipPct = parseFloat(document.getElementById('split-tip-pct')?.value) || 0;
        const people = parseInt(document.getElementById('split-people-count')?.value, 10) || 1;

        const tipAmount = total * (tipPct / 100);
        const grandTotal = total + tipAmount;
        const perPerson = people > 0 ? (grandTotal / people) : 0;

        const resEl = document.getElementById('split-result-amount');
        if (resEl) resEl.textContent = `₦${perPerson.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        const grandEl = document.getElementById('split-grand-total');
        if (grandEl) grandEl.textContent = `₦${grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };

    window.copyBillSplit = function () {
        const perPerson = document.getElementById('split-result-amount')?.textContent || '₦0.00';
        const people = document.getElementById('split-people-count')?.value || '1';
        const text = `Hey guys! Split bill breakdown from SpendWise:\n• Total: ${document.getElementById('split-grand-total')?.textContent}\n• Split ${people} ways: ${perPerson} per person.\nAccount: Main Bank / SpendWise Wallet.`;
        navigator.clipboard.writeText(text).then(() => {
            showToast('📋 Copied split summary to clipboard!');
        });
    };

    // ── 6. RECEIPT ATTACHMENT INFORMATION ───────────────────────────────────────
    window.openReceiptScanner = function () {
        const modal = document.getElementById('receipt-scanner-modal');
        if (modal) modal.classList.remove('hidden');
    };

    window.closeReceiptScanner = function () {
        const modal = document.getElementById('receipt-scanner-modal');
        if (modal) modal.classList.add('hidden');
    };

    // ── 7. REAL WEBAUTHN BIOMETRIC & PASSKEY AUTHENTICATOR ───────────────────────
    function getCsrfToken() {
        const cookies = document.cookie ? document.cookie.split('; ') : [];
        for (let i = 0; i < cookies.length; i++) {
            const parts = cookies[i].split('=');
            if (parts[0] === 'csrftoken') {
                return decodeURIComponent(parts[1]);
            }
        }
        return '';
    }

    function base64UrlToBytes(value) {
        const base64 = value.replace(/-/g, '+').replace(/_/g, '/');
        const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
        return Uint8Array.from(atob(padded), character => character.charCodeAt(0));
    }

    function bufferToBase64Url(buffer) {
        let binary = '';
        new Uint8Array(buffer).forEach(byte => { binary += String.fromCharCode(byte); });
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
    }

    function serializePasskeyCredential(credential) {
        const response = {
            clientDataJSON: bufferToBase64Url(credential.response.clientDataJSON),
        };
        if (credential.response.attestationObject) {
            response.attestationObject = bufferToBase64Url(credential.response.attestationObject);
            response.transports = credential.response.getTransports?.() || [];
        } else {
            response.authenticatorData = bufferToBase64Url(credential.response.authenticatorData);
            response.signature = bufferToBase64Url(credential.response.signature);
            response.userHandle = credential.response.userHandle
                ? bufferToBase64Url(credential.response.userHandle)
                : null;
        }
        return {
            id: credential.id,
            rawId: bufferToBase64Url(credential.rawId),
            type: credential.type,
            authenticatorAttachment: credential.authenticatorAttachment,
            clientExtensionResults: credential.getClientExtensionResults(),
            response,
        };
    }

    async function postPasskeyJson(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify(data),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(result.message || `Passkey request failed (${response.status}).`);
            error.isServerError = true;
            throw error;
        }
        return result;
    }

    function showPasskeyStatus(message, isError = false) {
        const status = document.getElementById('passkey-status');
        if (status) {
            status.textContent = message;
            status.classList.toggle('text-rose-500', isError);
            status.classList.toggle('text-emerald-600', !isError);
            status.classList.remove('hidden');
        }
        showToast(message);
    }

    function ensurePasskeyContext() {
        if (!window.PublicKeyCredential || !navigator.credentials) {
            showPasskeyStatus('This browser does not support passkeys. Sign in with your password instead.', true);
            return false;
        }
        if (!window.isSecureContext) {
            showPasskeyStatus('Passkeys require HTTPS. Open the secure SpendWise URL and try again.', true);
            return false;
        }
        if (window.location.hostname === '127.0.0.1') {
            const localUrl = new URL(window.location.href);
            localUrl.hostname = 'localhost';
            window.location.replace(localUrl.href);
            return false;
        }
        return true;
    }

    window.triggerBiometricAuth = async function () {
        if (!ensurePasskeyContext()) return;

        try {
            showPasskeyStatus('Choose a passkey, or select “Use another device” in your browser prompt. Keep Bluetooth on to use a nearby phone.');
            const options = await postPasskeyJson('/api/passkey/challenge/', {});
            options.challenge = base64UrlToBytes(options.challenge);
            options.allowCredentials = (options.allowCredentials || []).map(item => ({
                ...item,
                id: base64UrlToBytes(item.id),
                transports: ['internal'],
            }));
            if (!options.allowCredentials.length) {
                throw new Error('No local platform passkey is registered. Sign in with your password and create one first.');
            }
            const credential = await navigator.credentials.get({ publicKey: options });
            if (!credential) {
                showPasskeyStatus('No passkey was selected. Try again or sign in with your password.', true);
                return;
            }
            if (credential.authenticatorAttachment !== 'platform') {
                showPasskeyStatus('This passkey was not supplied by a local device authenticator. Use a platform passkey such as Windows Hello.', true);
                return;
            }

            const result = await postPasskeyJson('/api/passkey/verify/', serializePasskeyCredential(credential));
            if (result.status === 'success') {
                fireConfetti();
                showToast('✅ ' + (result.message || 'Passkey verified. Redirecting…'));
                setTimeout(() => {
                    window.location.href = result.redirect_url || '/dashboard/';
                }, 800);
            } else {
                showToast('❌ ' + (result.message || 'Passkey verification failed.'));
            }

        } catch (err) {
            console.warn('WebAuthn Passkey Error:', err);
            if (err.isServerError) {
                showPasskeyStatus(err.message, true);
            } else if (err.name === 'NotAllowedError') {
                showPasskeyStatus('No passkey was selected, or the request timed out. Try again or use your password.', true);
            } else if (err.name === 'AbortError') {
                showPasskeyStatus('Passkey sign-in was cancelled.', true);
            } else {
                showPasskeyStatus(err.message || 'Passkey sign-in failed. Please try again.', true);
            }
        }
    };

    window.registerPasskeyDevice = async function (deviceName = 'Biometric Passkey', username = '') {
        if (!ensurePasskeyContext()) return;

        try {
            const isSignup = Boolean(document.getElementById('signup-typewriter'));
            if (isSignup && !username.trim()) {
                showPasskeyStatus('Enter a username to create your account.', true);
                document.getElementById('id_username')?.focus();
                return;
            }
            showPasskeyStatus(isSignup ? 'Creating your account passkey…' : 'Starting passkey registration…');
            const options = await postPasskeyJson('/api/passkey/register/challenge/', { username });
            options.challenge = base64UrlToBytes(options.challenge);
            options.user.id = base64UrlToBytes(options.user.id);
            options.authenticatorSelection = {
                ...options.authenticatorSelection,
                authenticatorAttachment: 'platform',
            };
            options.excludeCredentials = (options.excludeCredentials || []).map(item => ({
                ...item,
                id: base64UrlToBytes(item.id),
            }));

            const credential = await navigator.credentials.create({ publicKey: options });
            if (!credential) {
                showPasskeyStatus('Passkey registration was cancelled.', true);
                return;
            }
            if (credential.authenticatorAttachment !== 'platform') {
                showPasskeyStatus('This browser did not create a local platform passkey. Use Windows Hello or another built-in authenticator.', true);
                return;
            }

            const result = await postPasskeyJson('/api/passkey/register/verify/', {
                ...serializePasskeyCredential(credential),
                deviceName,
            });
            if (result.status === 'success' && result.redirect_url) {
                fireConfetti();
                showToast('🎉 Account created with your passkey!');
                setTimeout(() => { window.location.href = result.redirect_url; }, 800);
            } else if (result.status === 'success') {
                fireConfetti();
                showToast('🎉 Passkey registered successfully!');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showToast('❌ ' + (result.message || 'Passkey registration failed.'));
            }
        } catch (err) {
            console.warn('Registration error:', err);
            if (err.isServerError) {
                showPasskeyStatus(err.message, true);
            } else if (err.name === 'NotAllowedError') {
                showPasskeyStatus('Registration was cancelled or timed out. Try again.', true);
            } else {
                showPasskeyStatus(err.message || 'Passkey registration failed. Please try again.', true);
            }
        }
    };

    // ── 8. CONFETTI ENGINE ───────────────────────────────────────────────────────
    window.fireConfetti = function () {
        const canvas = document.getElementById('confetti-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const pieces = [];
        const colors = ['#10b981', '#059669', '#06b6d4', '#f59e0b', '#f43f5e', '#ffffff'];

        for (let i = 0; i < 80; i++) {
            pieces.push({
                x: canvas.width / 2,
                y: canvas.height / 2,
                r: Math.random() * 6 + 4,
                d: Math.random() * 80,
                color: colors[Math.floor(Math.random() * colors.length)],
                tilt: Math.random() * 10 - 10,
                tiltAngleIncremental: (Math.random() * 0.07) + 0.05,
                tiltAngle: 0,
                vx: (Math.random() - 0.5) * 16,
                vy: (Math.random() - 0.5) * 16 - 4,
                gravity: 0.25
            });
        }

        let animationFrame;
        const render = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            let active = 0;

            pieces.forEach(p => {
                p.x += p.vx;
                p.y += p.vy;
                p.vy += p.gravity;
                p.tiltAngle += p.tiltAngleIncremental;
                p.tilt = Math.sin(p.tiltAngle) * 12;

                if (p.y < canvas.height) active++;

                ctx.beginPath();
                ctx.lineWidth = p.r / 2;
                ctx.strokeStyle = p.color;
                ctx.moveTo(p.x + p.tilt + (p.r / 4), p.y);
                ctx.lineTo(p.x + p.tilt, p.y + p.tilt + (p.r / 4));
                ctx.stroke();
            });

            if (active > 0) {
                animationFrame = requestAnimationFrame(render);
            } else {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                cancelAnimationFrame(animationFrame);
            }
        };

        render();
    };

    // ── TOAST NOTIFICATIONS ─────────────────────────────────────────────────────
    window.showToast = function (msg) {
        let toast = document.getElementById('global-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'global-toast';
            toast.className = 'fixed bottom-6 right-6 z-50 bg-slate-900/90 dark:bg-slate-800/95 text-white border border-slate-700/80 px-4 py-3 rounded-2xl shadow-2xl backdrop-blur-xl text-sm font-medium transition-all duration-300 transform translate-y-12 opacity-0 flex items-center gap-2';
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        toast.classList.remove('translate-y-12', 'opacity-0');
        setTimeout(() => {
            toast.classList.add('translate-y-12', 'opacity-0');
        }, 2800);
    };

    function escapeHtml(string) {
        const div = document.createElement('div');
        div.innerText = string;
        return div.innerHTML;
    }

    // ── INITIALIZATION ──────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        initPrivacyMode();
        initCommandPalette();

    });

})();
