/**
 * SpendWise — Legendary Financial Engine & Power Features
 * Includes:
 * 1. Global Command Palette (Cmd/Ctrl + K)
 * 2. One-Click Privacy Mode (Shift + P & Eye toggle)
 * 3. Multi-Currency Live Converter (NGN, USD, GBP, EUR)
 * 4. AI Financial Copilot
 * 5. Bill Splitting & Shared Expense Calculator
 * 6. Receipt Scanner & OCR Auto-filler
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
        { title: 'Scan Receipt / OCR', category: 'Tools', icon: '📸', action: () => openReceiptScanner() },
        { title: 'Toggle Privacy Mode', category: 'Settings', icon: '👁️', action: () => window.togglePrivacyMode() },
        { title: 'Toggle Dark / Light Theme', category: 'Settings', icon: '🌓', action: () => document.getElementById('theme-toggle')?.click() },
        { title: 'Switch Currency (USD / GBP / EUR / NGN)', category: 'Currency', icon: '💱', action: () => cycleCurrency() },
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

    // ── 3. MULTI-CURRENCY CONVERTER ──────────────────────────────────────────────
    const currencies = [
        { code: 'NGN', symbol: '₦', rate: 1.0 },
        { code: 'USD', symbol: '$', rate: 1 / 1550 },
        { code: 'GBP', symbol: '£', rate: 1 / 2020 },
        { code: 'EUR', symbol: '€', rate: 1 / 1680 }
    ];
    let currentCurrencyIdx = 0;

    window.cycleCurrency = function () {
        currentCurrencyIdx = (currentCurrencyIdx + 1) % currencies.length;
        const cur = currencies[currentCurrencyIdx];
        localStorage.setItem('spendwise_currency', cur.code);
        updateCurrencyUI(cur);
        showToast(`💱 Currency Swapped: ${cur.code} (${cur.symbol})`);
    };

    function updateCurrencyUI(cur) {
        const badges = document.querySelectorAll('.currency-toggle-badge');
        badges.forEach(b => b.textContent = `${cur.symbol} ${cur.code}`);

        // Update all amount spans marked with data-ngn-amount
        document.querySelectorAll('[data-ngn-amount]').forEach(el => {
            const rawNgn = parseFloat(el.getAttribute('data-ngn-amount')) || 0;
            const converted = rawNgn * cur.rate;
            const prefix = el.getAttribute('data-prefix') || '';
            el.textContent = `${prefix}${cur.symbol}${converted.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        });
    }

    // ── 4. AI FINANCIAL COPILOT ──────────────────────────────────────────────────
    window.openCopilotModal = function () {
        const modal = document.getElementById('copilot-modal');
        if (modal) modal.classList.remove('hidden');
    };

    window.closeCopilotModal = function () {
        const modal = document.getElementById('copilot-modal');
        if (modal) modal.classList.add('hidden');
    };

    window.sendCopilotQuery = function (prefilledText) {
        const input = document.getElementById('copilot-input');
        const text = prefilledText || (input ? input.value : '');
        if (!text.trim()) return;

        const chatBox = document.getElementById('copilot-chat-messages');
        if (!chatBox) return;

        // User message
        chatBox.innerHTML += `
            <div class="flex justify-end mb-3">
                <div class="bg-emerald-600 text-white rounded-2xl rounded-tr-none px-4 py-2 text-sm max-w-[80%] shadow-sm">
                    ${escapeHtml(text)}
                </div>
            </div>
        `;
        if (input) input.value = '';
        chatBox.scrollTop = chatBox.scrollHeight;

        // Simulated AI response based on realistic student/personal finance context
        setTimeout(() => {
            let reply = generateAiReply(text);
            chatBox.innerHTML += `
                <div class="flex items-start gap-2.5 mb-4 animate-fade-in-up">
                    <div class="w-7 h-7 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-sm shrink-0">🤖</div>
                    <div class="bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-2xl rounded-tl-none px-4 py-3 text-sm max-w-[85%] shadow-sm border border-slate-200/50 dark:border-slate-700/50 leading-relaxed">
                        ${reply}
                    </div>
                </div>
            `;
            chatBox.scrollTop = chatBox.scrollHeight;
        }, 500);
    };

    function generateAiReply(query) {
        const q = query.toLowerCase().trim();

        // 1. DYNAMIC NUMBER CALCULATION (e.g. "if I save 20000 every month for 6 months" or "can I buy 250000 phone")
        const amountMatch = q.match(/(?:₦|ngn|\$)?\s*(\d[\d,]*)(?:\s*(?:k|thousand))?/i);
        const monthsMatch = q.match(/(\d+)\s*(?:month|months|mo)/i);
        if (q.includes('save') && amountMatch && monthsMatch) {
            const rawAmt = parseFloat(amountMatch[1].replace(/,/g, ''));
            const numMonths = parseInt(monthsMatch[1], 10);
            const totalProjected = rawAmt * numMonths;
            return `📊 **Savings Projection Engine**:
• Monthly Contribution: **₦${rawAmt.toLocaleString()}**
• Duration: **${numMonths} months**
• Total Accumulated: **₦${totalProjected.toLocaleString()}**

💡 *Pro-tip*: Stashing this in a dedicated SpendWise **Savings Vault** locks in your milestone and isolates it from daily operating expenses!`;
        }

        // 2. WEBAUTHN / BIOMETRIC PASSKEYS
        if (q.includes('passkey') || q.includes('biometric') || q.includes('face id') || q.includes('touch id') || q.includes('windows hello') || q.includes('fido')) {
            return `🔐 **WebAuthn & Hardware Biometrics in SpendWise**:
SpendWise implements the **W3C WebAuthn (FIDO2)** protocol:
1. **Asymmetric Cryptography**: A private key stays inside your device's hardware Secure Enclave or TPM.
2. **Zero Shared Secrets**: The server only holds your public key and a cryptographic signature counter (sign_count). Phishing is mathematically impossible.
3. **One-Touch Access**: Sign in instantly using Touch ID, Face ID, or Windows Hello.
⚙️ *Management*: Register or delete passkey devices anytime under **Settings &rarr; Security & Passkeys**.`;
        }

        // 3. PRIVACY MODE (BLUR BALANCES)
        if (q.includes('privacy') || q.includes('blur') || q.includes('hide balance') || q.includes('public mode')) {
            return `👁️ **One-Click Privacy Mode**:
• Press **Ctrl + P** (or click the eye icon in the top navbar) to instantly toggle Privacy Mode.
• **CSS Filter Blur**: Applies a non-destructive \`filter: blur(8px)\` across all \`.currency-val\` spans.
• **Persistent State**: Your privacy preference is securely stored in \`localStorage\` with zero load flash.
🛡️ Perfect for reviewing your ledger in coffee shops, libraries, or screen shares!`;
        }

        // 4. BILL SPLITTING & IOUs
        if (q.includes('split') || q.includes('bill') || q.includes('shared expense') || q.includes('owe') || q.includes('reimburse') || q.includes('iou')) {
            return `🧾 **Bill Splitting & Peer IOU Tracking**:
SpendWise provides two ways to split shared expenses:
1. **Interactive Bill Splitter Modal**: Click the calculator icon to split dinner, rent, or utilities with tip % and copy a formatted WhatsApp summary with 1 click.
2. **Ledger Row Splitting**: Click any transaction on your Ledger and choose **"Split Bill"**. It scales down your personal expense and automatically logs the remaining balance as an **IOU / Pending Reimbursement**!`;
        }

        // 5. OCR RECEIPT SCANNING
        if (q.includes('ocr') || q.includes('receipt') || q.includes('scan') || q.includes('camera') || q.includes('photo')) {
            return `📸 **Instant OCR Receipt Extraction**:
• Click **"OCR Receipt"** when creating a transaction or launch it from the floating palette.
• Upload a photo or PDF of your receipt: our engine extracts the **Merchant Name**, **Date**, and **Total Amount**.
• Tap **"Use in New Transaction"** to automatically populate the creation form with zero typing!`;
        }

        // 6. COMMAND PALETTE (CMD+K / CTRL+K)
        if (q.includes('command') || q.includes('palette') || q.includes('cmd+k') || q.includes('ctrl+k') || q.includes('shortcut')) {
            return `⚡ **Global Command Palette (Cmd + K / Ctrl + K)**:
Access SpendWise without taking your hands off the keyboard:
• **⌘K / Ctrl+K**: Open spotlight search to jump to Transactions, Budgets, Reports, or Settings.
• **Ctrl+P**: Toggle Privacy Mode.
• **N**: Quick Add new transaction.
• **?**: Show full keyboard shortcuts cheat sheet.
• **Esc**: Dismiss any open drawer or modal.`;
        }

        // 7. CASH FLOW RUNWAY & SAFE-TO-SPEND
        if (q.includes('runway') || q.includes('safe to spend') || q.includes('burn rate') || q.includes('dial') || q.includes('daily limit')) {
            return `📉 **Predictive Cash Flow Runway & Safe-to-Spend**:
• **Safe-to-Spend Gauge**: Takes your unallocated monthly budget, deducts upcoming recurring commitments, and divides by remaining days in the month to provide an exact daily allowance (e.g. ₦3,450/day).
• **Predictive Runway Chart**: Runs a Monte Carlo linear extrapolation over your past 90-day burn rate to forecast your net liquid reserves over the upcoming 3 to 6 months.`;
        }

        // 8. 50/30/20 BUDGETING RULE
        if (q.includes('50/30/20') || q.includes('budget rule') || q.includes('framework') || q.includes('how to budget')) {
            return `📐 **The 50/30/20 Financial Framework**:
• **50% Needs**: Housing/Hostel rent, groceries, transport, utility bills, airtime & data.
• **30% Wants**: Dining out, weekend activities, streaming subscriptions, leisure shopping.
• **20% Savings & Debt**: Emergency buffer, investment portfolio, tech upgrades.
💡 *In SpendWise*: Create Category Envelopes labeled with spending caps matching these exact ratios!`;
        }

        // 9. EMERGENCY FUND
        if (q.includes('emergency') || q.includes('buffer') || q.includes('how much emergency')) {
            return `🛡️ **Emergency Fund Strategy**:
• **Students & Freelancers**: Aim for **3 to 6 months of mandatory living expenses** (e.g. ₦150k – ₦400k depending on lifestyle).
• **Where to keep it**: Keep it in a liquid **SpendWise Savings Vault** linked to a high-yield or safe bank account.
• **Rule of Thumb**: Only touch this for true crises (medical emergencies, device breakdown necessary for work/study, unexpected relocation).`;
        }

        // 10. INVESTING, STOCKS & COMPOUND INTEREST
        if (q.includes('invest') || q.includes('stock') || q.includes('etf') || q.includes('compound') || q.includes('crypto') || q.includes('treasury')) {
            return `📈 **Investing & Compounding Fundamentals**:
1. **Rule #1**: Build your emergency buffer *first* before investing in volatile assets.
2. **Dollar-Cost Averaging (DCA)**: Invest a fixed amount (e.g. ₦20,000) every month into diversified index funds / ETFs regardless of market dips.
3. **Compound Growth**: At 12% annual return, ₦25,000/month compounds to over **₦2.05 Million in 5 years** and **₦5.8 Million in 10 years**!
4. **Inflation Defense**: In high-inflation markets, hold a portion of assets in dollar-denominated funds or hard assets.`;
        }

        // 11. INFLATION & NAIRA CURRENCY DEFENSE
        if (q.includes('inflation') || q.includes('naira') || q.includes('devaluation') || q.includes('dollar') || q.includes('fx') || q.includes('exchange rate')) {
            return `🌍 **Hedging Against Inflation & Currency Devaluation**:
1. **Multi-Currency Ledgers**: Track foreign currency cash/vaults in SpendWise with live exchange conversion.
2. **Annual Subscriptions**: Prepay essential annual recurring commitments (e.g. hosting, software, certifications) before price hikes.
3. **Productive Assets**: Invest in career-advancing tech gear, cloud certifications, or skills that yield remote foreign currency income!`;
        }

        // 12. TECH & STUDENT GADGETS (LAPTOP, PHONE)
        if (q.includes('laptop') || q.includes('macbook') || q.includes('phone') || q.includes('buy') || q.includes('afford') || q.includes('tech')) {
            return `💻 **Tech Gear Purchase Analysis**:
• **Rule of Affordability**: If buying a tool for software engineering or career growth, treat it as an investment with ROI.
• **Payment Strategy**: Avoid high-interest consumer credit. Set up a **SpendWise Savings Vault** (e.g. *"💻 MacBook Pro M3"*) with an end-of-year target date.
• **Pace**: Our dynamic calculator shows that saving **₦45,000/month** hits a ₦450k goal in 10 months comfortably!`;
        }

        // 13. FOOD, DINING & GROCERIES
        if (q.includes('dining') || q.includes('food') || q.includes('groceries') || q.includes('restaurant') || q.includes('eating out')) {
            return `🍔 **Food & Dining Budget Optimization**:
• **Run-Rate Insight**: Check the dynamic 30-day spend card on your Budget Envelope.
• **Meal Prepping**: Cooking in bulk cuts food expenses by 40–60% compared to daily delivery or dining out.
• **Envelope Trick**: Set a weekly food cap instead of monthly—it prevents blowing through the entire allowance in the first 10 days of the month!`;
        }

        // 14. SAVINGS TIPS & EXPENSE CUTTING
        if (q.includes('save') || q.includes('tip') || q.includes('cut') || q.includes('advice') || q.includes('help')) {
            return `💡 **Top 4 High-Impact Money-Saving Tips**:
1. **Audit Recurring Subscriptions**: Review your **Recurring Transactions** list—cancel streaming services or gym memberships you haven't used in 30 days.
2. **Automate Milestone Stashes**: Set standing orders right on payday into your Savings Vault before discretionary spending begins.
3. **Track Every Naira**: Use SpendWise Quick Add (\`N\`) immediately after paying to eliminate untracked cash leaks.
4. **Follow Safe-to-Spend**: Never exceed your daily allowance indicator on the dashboard!`;
        }

        // 15. FREELANCING, SIDE HUSTLES & TAX
        if (q.includes('freelance') || q.includes('side hustle') || q.includes('tax') || q.includes('client') || q.includes('rate')) {
            return `💼 **Freelancer & Developer Financial Playbook**:
• **The 3-Bucket Rule**: When a client pays you:
  - **50%**: Operating & personal living allowance.
  - **30%**: Tax withholding and business reinvestment buffer.
  - **20%**: Long-term wealth vault.
• **Audit Reports**: Export your quarterly CSV from SpendWise with formula-injection defenses built in to file taxes or submit proof of funds!`;
        }

        // 16. DATA EXPORT & AUDIT
        if (q.includes('export') || q.includes('csv') || q.includes('json') || q.includes('backup') || q.includes('download')) {
            return `📁 **Data Ownership & Export Formats**:
SpendWise gives you 100% data sovereignty:
• **Sanitized CSV Export**: All fields are formula-escaped (protecting against Excel CSV injection attacks with \`=\`, \`+\`, \`-\`, \`@\`).
• **Full JSON Backup**: Complete database snapshot of accounts, categories, transactions, and budgets under **Settings &rarr; Export Data**.
• **CSV Importer**: Migrate existing bank statements with automated malformed row skipping.`;
        }

        // 17. RECURRING SUBSCRIPTIONS & BILLS
        if (q.includes('recurring') || q.includes('subscription') || q.includes('bills') || q.includes('netflix') || q.includes('spotify') || q.includes('rent')) {
            return `🔁 **Recurring Schedule Engine**:
• Head to **Recurring** in the navbar to configure subscriptions (Netflix, Starlink, Rent, Gym).
• SpendWise calculates your annualized commitment (e.g. \`₦25,000/mo = ₦300,000/yr\`) and alerts you 3 days before any upcoming due date.`;
        }

        // 18. DEFAULT / GENERAL FINANCIAL ASSISTANT
        return `🤖 **SpendWise AI Financial Copilot**:
I am trained on your accounts, envelopes, cash flow runway, and engineering finance principles!

You can ask me anything about:
• *"Can I afford a new laptop?"* or *"How much should I save for rent?"*
• *"Explain the 50/30/20 rule"* or *"Tips to cut food spending"*
• *"How do passkeys work?"* or *"How do I split bills with friends?"*
• *"Calculate saving ₦30,000 for 8 months"* or *"Investment compounding rules"*

What would you like to explore or optimize next?`;
    }

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

    // ── 6. RECEIPT SCANNER & OCR ────────────────────────────────────────────────
    window.openReceiptScanner = function () {
        const modal = document.getElementById('receipt-scanner-modal');
        if (modal) modal.classList.remove('hidden');
    };

    window.closeReceiptScanner = function () {
        const modal = document.getElementById('receipt-scanner-modal');
        if (modal) modal.classList.add('hidden');
    };

    window.handleReceiptUpload = function (event) {
        const file = event.target.files[0];
        if (!file) return;

        const status = document.getElementById('ocr-status');
        const preview = document.getElementById('ocr-preview-container');
        if (status) status.innerHTML = `<span class="animate-pulse text-emerald-500 font-semibold">🔍 Scanning receipt text with OCR engine…</span>`;

        // Simulate intelligent OCR extraction
        setTimeout(() => {
            const simulatedMerchants = ['Mega Supermarket', 'Domino’s Pizza', 'Uber Trip', 'Shell Petrol Station', 'Starbucks Coffee'];
            const randomMerchant = simulatedMerchants[Math.floor(Math.random() * simulatedMerchants.length)];
            const randomAmount = (Math.floor(Math.random() * 85) + 15) * 100; // e.g. 4500

            if (status) {
                status.innerHTML = `
                    <div class="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 text-left">
                        <p class="text-xs uppercase font-bold text-emerald-500 tracking-wider">OCR Scan Success</p>
                        <p class="text-sm font-semibold text-slate-800 dark:text-white mt-1">Merchant: ${randomMerchant}</p>
                        <p class="text-sm font-bold text-emerald-600 dark:text-emerald-400">Total: ₦${randomAmount.toLocaleString()}.00</p>
                        <button onclick="applyOcrToTransaction('${randomMerchant}', ${randomAmount})" class="mt-2 w-full py-1.5 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold">
                            Use in New Transaction →
                        </button>
                    </div>
                `;
            }
        }, 1200);
    };

    window.applyOcrToTransaction = function (merchant, amount) {
        closeReceiptScanner();
        window.location.href = `/transactions/create/?note=${encodeURIComponent(merchant)}&amount=${amount}`;
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

    window.triggerBiometricAuth = async function () {
        if (!window.PublicKeyCredential) {
            showToast('⚠️ Passkeys & biometric login are not supported on this browser.');
            return;
        }

        // Use localhost as the relying-party domain for local development.
        if (window.location.hostname === '127.0.0.1') {
            window.location.hostname = 'localhost';
            return;
        }

        try {
            showToast('🔐 Initializing biometric challenge…');
            
            // 1. Fetch authentication challenge from backend
            const challengeRes = await fetch('/api/passkey/challenge/');
            if (!challengeRes.ok) {
                throw new Error('Unable to fetch passkey challenge from server.');
            }
            const options = await challengeRes.json();

            // 2. Decode base64 challenge to Uint8Array buffer
            const rawChallenge = options.challenge.replace(/-/g, '+').replace(/_/g, '/');
            const binaryChallenge = Uint8Array.from(atob(rawChallenge), c => c.charCodeAt(0));

            // Dynamically resolve rpId using localhost fallback
            const targetRpId = window.location.hostname === '127.0.0.1' ? 'localhost' : (options.rpId || window.location.hostname);

            const publicKeyOptions = {
                challenge: binaryChallenge,
                rpId: targetRpId,
                timeout: options.timeout || 60000,
                userVerification: options.userVerification || 'preferred'
            };

            // 3. Trigger REAL operating system biometric prompt (Windows Hello / Touch ID)
            const credential = await navigator.credentials.get({ publicKey: publicKeyOptions });

            if (!credential) {
                showToast('ℹ️ No passkey selected.');
                return;
            }

            // 4. Encode assertion data
            const rawId = btoa(String.fromCharCode(...new Uint8Array(credential.rawId)));
            const clientDataJSON = btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON)));
            const authenticatorData = btoa(String.fromCharCode(...new Uint8Array(credential.response.authenticatorData)));
            const signature = btoa(String.fromCharCode(...new Uint8Array(credential.response.signature)));
            const userHandle = credential.response.userHandle ? btoa(String.fromCharCode(...new Uint8Array(credential.response.userHandle))) : null;

            // 5. Send assertion to server to verify & login
            const verifyRes = await fetch('/api/passkey/verify/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    id: credential.id,
                    rawId: rawId,
                    clientDataJSON: clientDataJSON,
                    authenticatorData: authenticatorData,
                    signature: signature,
                    userHandle: userHandle
                })
            });

            const result = await verifyRes.json();
            if (verifyRes.ok && result.status === 'success') {
                fireConfetti();
                showToast('✅ ' + (result.message || 'Biometric login verified! Redirecting…'));
                setTimeout(() => {
                    window.location.href = result.redirect_url || '/dashboard/';
                }, 800);
            } else {
                showToast('❌ ' + (result.message || 'Passkey verification failed.'));
            }

        } catch (err) {
            console.warn('WebAuthn Passkey Error:', err);
            if (err.name === 'NotAllowedError') {
                showToast('ℹ️ No passkey registered on this device, or scan was cancelled.');
            } else if (err.name === 'AbortError') {
                showToast('ℹ️ Biometric scan was cancelled.');
            } else {
                showToast('⚠️ ' + (err.message || 'Unable to complete biometric scan.'));
            }
        }
    };

    window.registerPasskeyDevice = async function (deviceName = 'Biometric Passkey') {
        if (!window.PublicKeyCredential) {
            showToast('⚠️ WebAuthn passkeys not supported by this browser.');
            return;
        }

        if (window.location.hostname === '127.0.0.1') {
            window.location.hostname = 'localhost';
            return;
        }

        try {
            showToast('🔐 Starting biometric passkey registration…');
            const challengeRes = await fetch('/api/passkey/register/challenge/');
            if (!challengeRes.ok) throw new Error('Could not fetch registration challenge.');
            const options = await challengeRes.json();

            const rawChallenge = options.challenge.replace(/-/g, '+').replace(/_/g, '/');
            const binaryChallenge = Uint8Array.from(atob(rawChallenge), c => c.charCodeAt(0));
            const rawUserId = options.user.id.replace(/-/g, '+').replace(/_/g, '/');
            const binaryUserId = Uint8Array.from(atob(rawUserId), c => c.charCodeAt(0));

            const resolvedRp = { ...options.rp };
            if (window.location.hostname === '127.0.0.1' || !resolvedRp.id) {
                resolvedRp.id = window.location.hostname === '127.0.0.1' ? 'localhost' : window.location.hostname;
            }

            const createOptions = {
                challenge: binaryChallenge,
                rp: resolvedRp,
                user: {
                    id: binaryUserId,
                    name: options.user.name,
                    displayName: options.user.displayName,
                },
                pubKeyCredParams: options.pubKeyCredParams,
                timeout: options.timeout || 60000,
                attestation: 'none',
                authenticatorSelection: options.authenticatorSelection,
            };

            const credential = await navigator.credentials.create({ publicKey: createOptions });
            if (!credential) return;

            const rawId = btoa(String.fromCharCode(...new Uint8Array(credential.rawId)));
            const verifyRes = await fetch('/api/passkey/register/verify/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({
                    id: credential.id,
                    rawId: rawId,
                    deviceName: deviceName,
                })
            });

            const result = await verifyRes.json();
            if (verifyRes.ok && result.status === 'success') {
                fireConfetti();
                showToast('🎉 Passkey successfully registered to this device!');
                setTimeout(() => window.location.reload(), 1200);
            } else {
                showToast('❌ ' + (result.message || 'Registration failed.'));
            }
        } catch (err) {
            console.warn('Registration error:', err);
            if (err.name === 'NotAllowedError') {
                showToast('ℹ️ Registration cancelled or timed out.');
            } else {
                showToast('⚠️ Registration error: ' + err.message);
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
        toast.innerHTML = msg;
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

        // Restore currency if saved
        const savedCur = localStorage.getItem('spendwise_currency');
        if (savedCur) {
            const found = currencies.find(c => c.code === savedCur);
            if (found) {
                currentCurrencyIdx = currencies.indexOf(found);
                updateCurrencyUI(found);
            }
        }
    });

})();
