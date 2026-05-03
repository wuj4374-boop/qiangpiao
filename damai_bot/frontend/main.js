/**
 * 大麦抢票系统 - 前端主逻辑
 *
 * 本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。
 * 请勿用于任何商业或非法用途。
 *
 * 技术要点：
 * - 单页应用（SPA）架构
 * - DOM 操作与事件处理
 * - 实时日志展示（WebSocket 接收）
 * - 任务状态管理与 UI 同步
 * - 免责声明弹窗（localStorage 持久化同意状态）
 *
 * 作者：小吴 (Xiao Wu)
 * 许可证：MIT
 */

document.addEventListener('DOMContentLoaded', function() {
    // 全局状态
    const state = {
        currentTaskId: null,
        currentGroupId: null,
        currentTaskStatus: null,
        isPolling: false,
        pollInterval: null,
        useWebSocket: true, // WebSocket优先
        webSocketConnected: false,
        webSocketFallback: false, // WebSocket失败后降级到轮询
        logs: [],
        maxLogs: 1000,
        connectionChecked: false,
        lastUpdate: null,
        successSoundPlayed: false,
        // 多账号相关
        accounts: [],
        selectedAccountIds: [],
        accountTasks: {}, // accountId -> {taskId, status, attempt}
        qrLoginAccountId: null, // 当前正在扫码登录的账号ID
    };

    // DOM 元素
    const elements = {
        // 登录面板
        loginPanel: document.getElementById('loginPanel'),
        mainPanel: document.getElementById('mainPanel'),
        username: document.getElementById('username'),
        password: document.getElementById('password'),
        apiUrl: document.getElementById('apiUrl'),
        loginBtn: document.getElementById('loginBtn'),
        logoutBtn: document.getElementById('logoutBtn'),
        userStatus: document.getElementById('currentUser'),
        connectionStatus: document.getElementById('connectionStatus'),

        // 大麦网账号管理面板
        damaiLoginPanel: document.getElementById('damaiLoginPanel'),
        accountList: document.getElementById('accountList'),
        addAccountBtn: document.getElementById('addAccountBtn'),
        testAllAccountsBtn: document.getElementById('testAllAccountsBtn'),
        qrcodeStatus: document.getElementById('qrcodeStatus'),
        goToMainBtn: document.getElementById('goToMainBtn'),
        backToLoginBtn: document.getElementById('backToLoginBtn'),
        // 账号选择（主面板）
        accountCheckboxes: document.getElementById('accountCheckboxes'),
        accountTasksSection: document.getElementById('accountTasksSection'),
        accountTasksList: document.getElementById('accountTasksList'),

        // 任务配置
        eventId: document.getElementById('eventId'),
        ticketCount: document.getElementById('ticketCount'),
        concertName: document.getElementById('concertName'),
        city: document.getElementById('city'),
        session: document.getElementById('session'),
        price: document.getElementById('price'),
        retryCount: document.getElementById('retryCount'),
        refreshInterval: document.getElementById('refreshInterval'),
        startTime: document.getElementById('startTime'),

        // 按钮
        startBtn: document.getElementById('startBtn'),
        stopBtn: document.getElementById('stopBtn'),
        clearLogsBtn: document.getElementById('clearLogsBtn'),

        // 状态显示
        currentStatus: document.getElementById('currentStatus'),
        taskId: document.getElementById('taskId'),
        attemptCount: document.getElementById('attemptCount'),
        successCount: document.getElementById('successCount'),
        lastUpdate: document.getElementById('lastUpdate'),
        backendStatus: document.getElementById('backendStatus'),
        latency: document.getElementById('latency'),
        captchaStatus: document.getElementById('captchaStatus'),

        // 日志
        logContainer: document.getElementById('logContainer'),
        logCount: document.getElementById('logCount'),
        lastLogTime: document.getElementById('lastLogTime'),
        totalLogs: document.getElementById('totalLogs'),
        autoScroll: document.getElementById('autoScroll'),
        playSound: document.getElementById('playSound'),

        // 模态框
        successModal: document.getElementById('successModal'),
        closeModal: document.getElementById('closeModal'),
        successConcert: document.getElementById('successConcert'),
        successSession: document.getElementById('successSession'),
        successPrice: document.getElementById('successPrice'),
        successOrderLink: document.getElementById('successOrderLink'),
        playSuccessSound: document.getElementById('playSuccessSound'),
        copyOrderLink: document.getElementById('copyOrderLink'),

        // 音频
        successSound: document.getElementById('successSound'),
        errorSound: document.getElementById('errorSound'),
        startSound: document.getElementById('startSound'),

        // 免责声明
        disclaimerModal: document.getElementById('disclaimerModal'),
        agreeCheckbox: document.getElementById('agreeCheckbox'),
        agreeBtn: document.getElementById('agreeBtn'),
        disagreeBtn: document.getElementById('disagreeBtn'),

        // 观演人
        attendees: document.getElementById('attendees'),
        importAttendees: document.getElementById('importAttendees'),
        clearAttendees: document.getElementById('clearAttendees'),

        // 其他
        currentTime: document.getElementById('currentTime')
    };

    // 初始化
    function init() {
        // 检查免责声明是否已同意
        const disclaimerAgreed = localStorage.getItem('disclaimerAgreed') === 'true';

        if (disclaimerAgreed) {
            // 已同意，隐藏免责声明模态框，显示容器，继续初始化
            elements.disclaimerModal.style.display = 'none';
            document.querySelector('.container').style.display = 'block';
            continueInit();
        } else {
            // 未同意，显示免责声明模态框，绑定免责声明事件
            elements.disclaimerModal.style.display = 'block';
            document.querySelector('.container').style.display = 'none';
            // 绑定免责声明事件
            elements.agreeCheckbox.addEventListener('change', toggleAgreeButton);
            elements.agreeBtn.addEventListener('click', handleDisclaimerAgree);
            elements.disagreeBtn.addEventListener('click', handleDisclaimerDisagree);
            // 初始化同意按钮状态
            toggleAgreeButton();
        }
    }

    // 免责声明处理
    function handleDisclaimerAgree() {
        if (!elements.agreeCheckbox.checked) {
            alert('请先阅读并同意免责声明');
            return;
        }
        // 保存同意状态
        localStorage.setItem('disclaimerAgreed', 'true');
        // 隐藏免责声明模态框
        elements.disclaimerModal.style.display = 'none';
        // 显示主容器
        document.querySelector('.container').style.display = 'block';
        // 继续正常初始化
        continueInit();
    }

    function handleDisclaimerDisagree() {
        const confirmExit = confirm('您必须同意免责声明才能使用本软件。\n\n如不同意，软件将退出。');
        if (confirmExit) {
            // 关闭窗口（在Electron中）
            if (typeof window.electron !== 'undefined') {
                window.electron.ipcRenderer.send('close-app');
            } else {
                // 在浏览器中，无法直接关闭窗口，显示警告
                alert('请关闭此浏览器标签页以退出。');
                elements.disclaimerModal.style.display = 'block';
            }
        }
    }

    function toggleAgreeButton() {
        elements.agreeBtn.disabled = !elements.agreeCheckbox.checked;
    }

    function continueInit() {
        // 更新当前时间
        updateCurrentTime();
        setInterval(updateCurrentTime, 1000);

        // 检查本地存储的API地址
        const savedApiUrl = localStorage.getItem('damai_api_url');
        if (savedApiUrl) {
            elements.apiUrl.value = savedApiUrl;
            api.baseUrl = savedApiUrl;
            api.apiPrefix = `${savedApiUrl}/api/v1`;
        }

        // 检查是否已登录
        if (api.isAuthenticated()) {
            showDamaiLoginPanel();
            checkConnection();
        } else {
            showLoginPanel();
        }

        // 绑定事件（除了免责声明事件）
        bindEvents();

        // 添加初始日志
        addLog('系统初始化完成。', 'system');
    }

    // 观演人处理
    function handleImportAttendees() {
        // 创建虚拟文件输入元素
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = '.csv,.txt';
        fileInput.onchange = async (event) => {
            const file = event.target.files[0];
            if (!file) return;

            try {
                const text = await file.text();
                // 简单解析CSV：每行逗号分隔
                const lines = text.trim().split('\n');
                const attendees = [];
                for (const line of lines) {
                    const trimmed = line.trim();
                    if (trimmed && !trimmed.startsWith('#')) {
                        const parts = trimmed.split(',');
                        if (parts.length >= 3) {
                            attendees.push({
                                name: parts[0].trim(),
                                idCard: parts[1].trim(),
                                phone: parts[2].trim()
                            });
                        }
                    }
                }
                // 格式化为文本区域内容
                const formatted = attendees.map(a => `${a.name},${a.idCard},${a.phone}`).join('\n');
                elements.attendees.value = formatted;
                addLog(`已导入 ${attendees.length} 个观演人`, 'success');
            } catch (error) {
                console.error('导入CSV失败:', error);
                addLog('导入CSV失败，请检查文件格式', 'error');
            }
        };
        fileInput.click();
    }

    function handleClearAttendees() {
        if (elements.attendees.value.trim()) {
            const confirmClear = confirm('确定要清空观演人列表吗？');
            if (confirmClear) {
                elements.attendees.value = '';
                addLog('观演人列表已清空', 'system');
            }
        }
    }

    // 绑定事件
    function bindEvents() {
        // 免责声明事件
        if (elements.agreeCheckbox) {
            elements.agreeCheckbox.addEventListener('change', toggleAgreeButton);
        }
        if (elements.agreeBtn) {
            elements.agreeBtn.addEventListener('click', handleDisclaimerAgree);
        }
        if (elements.disagreeBtn) {
            elements.disagreeBtn.addEventListener('click', handleDisclaimerDisagree);
        }

        // 登录
        elements.loginBtn.addEventListener('click', handleLogin);
        elements.logoutBtn.addEventListener('click', handleLogout);
        elements.apiUrl.addEventListener('change', saveApiUrl);

        // 大麦网登录
        if (elements.addAccountBtn) {
            elements.addAccountBtn.addEventListener('click', handleAddAccount);
        }
        if (elements.testAllAccountsBtn) {
            elements.testAllAccountsBtn.addEventListener('click', handleTestAllAccounts);
        }
        if (elements.goToMainBtn) {
            elements.goToMainBtn.addEventListener('click', function() {
                showMainPanel();
                checkConnection();
            });
        }
        if (elements.backToLoginBtn) {
            elements.backToLoginBtn.addEventListener('click', function() {
                showLoginPanel();
            });
        }

        // 观演人事件
        if (elements.importAttendees) {
            elements.importAttendees.addEventListener('click', handleImportAttendees);
        }
        if (elements.clearAttendees) {
            elements.clearAttendees.addEventListener('click', handleClearAttendees);
        }

        // 表单提交
        elements.startBtn.addEventListener('click', startTicketTask);
        elements.stopBtn.addEventListener('click', stopTicketTask);
        elements.clearLogsBtn.addEventListener('click', clearLogs);

        // 模态框
        elements.closeModal.addEventListener('click', hideSuccessModal);
        elements.playSuccessSound.addEventListener('click', playSuccessSound);
        elements.copyOrderLink.addEventListener('click', copyOrderLink);
        window.addEventListener('click', function(event) {
            if (event.target === elements.successModal) {
                hideSuccessModal();
            }
        });

        // 输入框回车键提交
        elements.password.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') handleLogin();
        });

        // 配置输入框变化
        [elements.concertName, elements.city, elements.session, elements.price].forEach(input => {
            input.addEventListener('change', updateTaskSummary);
        });
    }

    // 登录处理
    async function handleLogin() {
        const username = elements.username.value.trim();
        const password = elements.password.value.trim();
        const apiUrl = elements.apiUrl.value.trim();

        if (!username || !password || !apiUrl) {
            alert('请输入用户名、密码和API地址');
            return;
        }

        // 保存API地址
        saveApiUrl();

        // 更新API实例
        api.baseUrl = apiUrl;
        api.apiPrefix = `${apiUrl}/api/v1`;

        elements.loginBtn.disabled = true;
        elements.loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 登录中...';

        try {
            addLog(`正在连接到 ${apiUrl}...`, 'info');

            // 测试连接
            const health = await api.healthCheck();
            if (health.status !== 'healthy') {
                throw new Error('后端服务不可用，请检查服务是否启动');
            }

            // 执行登录
            const response = await api.login(username, password);

            if (response.success) {
                addLog(`登录成功！欢迎 ${response.data.user.username}`, 'success');
                showDamaiLoginPanel();
                updateUserStatus(response.data.user);
                checkConnection();
            } else {
                throw new Error(response.message || '登录失败');
            }
        } catch (error) {
            console.error('登录失败:', error);
            addLog(`登录失败: ${error.message}`, 'error');
            if (error.status === 401) {
                alert('用户名或密码错误');
            } else if (error.status === 404) {
                alert('API地址错误或后端服务未启动');
            } else {
                alert(`登录失败: ${error.message}`);
            }
        } finally {
            elements.loginBtn.disabled = false;
            elements.loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> 登录系统';
        }
    }

    // 保存API地址
    function saveApiUrl() {
        const apiUrl = elements.apiUrl.value.trim();
        if (apiUrl) {
            localStorage.setItem('damai_api_url', apiUrl);
        }
    }

    // 退出登录
    function handleLogout() {
        api.logout();
        addLog('已退出登录。', 'system');
        showLoginPanel();
    }

    // 检查大麦网登录状态
    async function checkDamaiLoginStatus() {
        if (!elements.damaiLoginPanel) return;
        try {
            const res = await api.testLoginStatus();
            if (res && res.logged_in) {
                elements.damaiLoginStatus.textContent = '已登录';
                elements.damaiLoginStatus.className = 'status-value status-running';
                elements.damaiNickname.textContent = res.nickname || '已登录';
                elements.goToMainBtn.disabled = false;
                elements.qrcodeStatus.style.display = 'none';
            } else {
                elements.damaiLoginStatus.textContent = '未登录';
                elements.damaiLoginStatus.className = 'status-value status-idle';
                elements.damaiNickname.textContent = '-';
                elements.goToMainBtn.disabled = true;
            }
        } catch {
            elements.damaiLoginStatus.textContent = '未登录';
            elements.damaiLoginStatus.className = 'status-value status-idle';
            elements.damaiNickname.textContent = '-';
            elements.goToMainBtn.disabled = true;
        }
    }

    // ===================== 多账号管理 =====================

    // 渲染账号列表
    async function renderAccountList() {
        if (!elements.accountList) return;
        try {
            const res = await api.getAccounts();
            state.accounts = res.accounts || [];
        } catch (error) {
            console.error('获取账号列表失败:', error);
            state.accounts = [];
        }

        if (state.accounts.length === 0) {
            elements.accountList.innerHTML = '<div class="account-empty">暂无账号，请点击下方"添加账号"</div>';
        } else {
            elements.accountList.innerHTML = state.accounts.map(acc => `
                <div class="account-card" data-id="${acc.id}">
                    <div class="account-info">
                        <span class="account-nickname">${acc.nickname || '未登录_' + acc.id.slice(-4)}</span>
                        <span class="account-status ${acc.status === 'logged_in' ? 'logged_in' : 'not_logged_in'}">
                            ${acc.status === 'logged_in' ? '已登录' : '未登录'}
                        </span>
                    </div>
                    <div class="account-actions">
                        <button class="btn-small btn-primary account-login-btn" data-id="${acc.id}">
                            <i class="fas fa-qrcode"></i> 扫码
                        </button>
                        <button class="btn-small btn-secondary account-test-btn" data-id="${acc.id}">
                            <i class="fas fa-vial"></i> 检测
                        </button>
                        <button class="btn-small btn-danger account-delete-btn" data-id="${acc.id}">
                            <i class="fas fa-trash"></i> 删除
                        </button>
                    </div>
                </div>
            `).join('');

            // 绑定事件
            elements.accountList.querySelectorAll('.account-login-btn').forEach(btn => {
                btn.addEventListener('click', () => handleAccountLogin(btn.dataset.id));
            });
            elements.accountList.querySelectorAll('.account-test-btn').forEach(btn => {
                btn.addEventListener('click', () => handleTestAccount(btn.dataset.id));
            });
            elements.accountList.querySelectorAll('.account-delete-btn').forEach(btn => {
                btn.addEventListener('click', () => handleDeleteAccount(btn.dataset.id));
            });
        }

        // 更新"进入抢票"按钮状态
        const hasLoggedIn = state.accounts.some(a => a.status === 'logged_in');
        elements.goToMainBtn.disabled = !hasLoggedIn;
    }

    // 渲染账号复选框（主面板）
    async function renderAccountCheckboxes() {
        if (!elements.accountCheckboxes) return;
        try {
            const res = await api.getAccounts();
            state.accounts = res.accounts || [];
        } catch (error) {
            state.accounts = [];
        }

        const loggedInAccounts = state.accounts.filter(a => a.status === 'logged_in');
        if (loggedInAccounts.length === 0) {
            elements.accountCheckboxes.innerHTML = '<div class="account-empty">暂无已登录账号，请先在账号管理中登录</div>';
            return;
        }

        elements.accountCheckboxes.innerHTML = loggedInAccounts.map(acc => `
            <label class="account-checkbox-item">
                <input type="checkbox" value="${acc.id}" class="account-checkbox" checked>
                <span class="account-checkbox-label">${acc.nickname || '账号_' + acc.id.slice(-4)}</span>
            </label>
        `).join('');

        // 默认全选
        state.selectedAccountIds = loggedInAccounts.map(a => a.id);

        // 监听变化
        elements.accountCheckboxes.querySelectorAll('.account-checkbox').forEach(cb => {
            cb.addEventListener('change', () => {
                state.selectedAccountIds = Array.from(
                    elements.accountCheckboxes.querySelectorAll('.account-checkbox:checked')
                ).map(el => el.value);
            });
        });
    }

    // 添加账号
    async function handleAddAccount() {
        elements.addAccountBtn.disabled = true;
        elements.addAccountBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 添加中...';
        try {
            const res = await api.addAccount();
            if (res && res.id) {
                addLog(`账号 ${res.id} 已添加，请扫码登录`, 'success');
                await renderAccountList();
            }
        } catch (error) {
            addLog(`添加账号失败: ${error.message}`, 'error');
        } finally {
            elements.addAccountBtn.disabled = false;
            elements.addAccountBtn.innerHTML = '<i class="fas fa-plus"></i> 添加账号';
        }
    }

    // 删除账号
    async function handleDeleteAccount(accountId) {
        if (!confirm('确定要删除此账号吗？相关的 Cookie 也将被清除。')) return;
        try {
            await api.deleteAccount(accountId);
            addLog(`账号 ${accountId} 已删除`, 'success');
            await renderAccountList();
        } catch (error) {
            addLog(`删除账号失败: ${error.message}`, 'error');
        }
    }

    // 账号扫码登录
    async function handleAccountLogin(accountId) {
        state.qrLoginAccountId = accountId;
        const btn = elements.accountList.querySelector(`.account-login-btn[data-id="${accountId}"]`);
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }

        elements.qrcodeStatus.style.display = 'flex';
        elements.qrcodeStatus.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>正在打开登录页面...</span>';
        elements.qrcodeStatus.style.borderColor = '';
        elements.qrcodeStatus.style.color = '';

        try {
            const res = await api.loginAccount(accountId);
            if (res && res.status === 'waiting') {
                elements.qrcodeStatus.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>请打开大麦APP扫描二维码...</span>';
                addLog(`账号 ${accountId} 请扫码登录`, 'info');

                // 轮询登录状态
                let attempts = 0;
                const maxAttempts = 40;
                const poll = setInterval(async () => {
                    attempts++;
                    if (attempts > maxAttempts) {
                        clearInterval(poll);
                        elements.qrcodeStatus.innerHTML = '<i class="fas fa-times-circle"></i> <span>二维码已过期，请重新获取</span>';
                        elements.qrcodeStatus.style.borderColor = 'var(--error-color)';
                        elements.qrcodeStatus.style.color = 'var(--error-color)';
                        if (btn) {
                            btn.disabled = false;
                            btn.innerHTML = '<i class="fas fa-qrcode"></i> 扫码';
                        }
                        state.qrLoginAccountId = null;
                        return;
                    }
                    try {
                        const statusRes = await api.testAccountLogin(accountId);
                        if (statusRes && statusRes.logged_in) {
                            clearInterval(poll);
                            elements.qrcodeStatus.innerHTML = '<i class="fas fa-check-circle"></i> <span>登录成功！</span>';
                            elements.qrcodeStatus.style.borderColor = 'var(--success-color)';
                            elements.qrcodeStatus.style.color = 'var(--success-color)';
                            addLog(`账号 ${statusRes.nickname || accountId} 登录成功！`, 'success');
                            state.qrLoginAccountId = null;
                            await renderAccountList();
                        }
                    } catch {
                        // 继续等待
                    }
                }, 3000);
            } else {
                throw new Error(res?.message || '启动扫码登录失败');
            }
        } catch (error) {
            elements.qrcodeStatus.innerHTML = `<i class="fas fa-times-circle"></i> <span>启动登录失败: ${error.message}</span>`;
            elements.qrcodeStatus.style.borderColor = 'var(--error-color)';
            elements.qrcodeStatus.style.color = 'var(--error-color)';
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-qrcode"></i> 扫码';
            }
            state.qrLoginAccountId = null;
            addLog(`启动登录失败: ${error.message}`, 'error');
        }
    }

    // 检测单个账号登录状态
    async function handleTestAccount(accountId) {
        const btn = elements.accountList.querySelector(`.account-test-btn[data-id="${accountId}"]`);
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }
        try {
            const res = await api.testAccountLogin(accountId);
            if (res && res.logged_in) {
                addLog(`账号 ${res.nickname || accountId} 登录状态正常`, 'success');
            } else {
                addLog(`账号 ${accountId} 未登录`, 'warning');
            }
            await renderAccountList();
        } catch (error) {
            addLog(`检测账号 ${accountId} 失败: ${error.message}`, 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-vial"></i> 检测';
            }
        }
    }

    // 检测所有账号
    async function handleTestAllAccounts() {
        elements.testAllAccountsBtn.disabled = true;
        elements.testAllAccountsBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 检测中...';
        try {
            for (const acc of state.accounts) {
                try {
                    const res = await api.testAccountLogin(acc.id);
                    if (res && res.logged_in) {
                        addLog(`账号 ${res.nickname || acc.id} 已登录`, 'success');
                    } else {
                        addLog(`账号 ${acc.id} 未登录`, 'warning');
                    }
                } catch (e) {
                    addLog(`检测账号 ${acc.id} 失败: ${e.message}`, 'error');
                }
            }
            await renderAccountList();
        } finally {
            elements.testAllAccountsBtn.disabled = false;
            elements.testAllAccountsBtn.innerHTML = '<i class="fas fa-vial"></i> 检测全部';
        }
    }

    // 大麦网扫码登录
    async function handleQrcodeLogin() {
        elements.qrcodeLoginBtn.disabled = true;
        elements.qrcodeLoginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 获取二维码...';
        elements.qrcodeStatus.style.display = 'flex';
        elements.qrcodeStatus.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>正在获取二维码...</span>';

        try {
            const res = await api.startQrcodeLogin();
            if (res && res.success) {
                elements.qrcodeStatus.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>请打开大麦APP扫描二维码...</span>';
                addLog('二维码已获取，请打开大麦APP扫码登录', 'info');

                // 轮询登录状态
                let attempts = 0;
                const maxAttempts = 60; // 最多等60秒
                const pollInterval = setInterval(async () => {
                    attempts++;
                    if (attempts > maxAttempts) {
                        clearInterval(pollInterval);
                        elements.qrcodeStatus.innerHTML = '<i class="fas fa-times-circle"></i> <span>二维码已过期，请重新获取</span>';
                        elements.qrcodeStatus.style.borderColor = 'var(--error-color)';
                        elements.qrcodeStatus.style.color = 'var(--error-color)';
                        elements.qrcodeLoginBtn.disabled = false;
                        elements.qrcodeLoginBtn.innerHTML = '<i class="fas fa-qrcode"></i> 扫码登录';
                        return;
                    }
                    try {
                        const statusRes = await api.testLoginStatus();
                        if (statusRes && statusRes.logged_in) {
                            clearInterval(pollInterval);
                            elements.damaiLoginStatus.textContent = '已登录';
                            elements.damaiLoginStatus.className = 'status-value status-running';
                            elements.damaiNickname.textContent = statusRes.nickname || '已登录';
                            elements.goToMainBtn.disabled = false;
                            elements.qrcodeStatus.innerHTML = '<i class="fas fa-check-circle"></i> <span>登录成功！</span>';
                            elements.qrcodeStatus.style.borderColor = 'var(--success-color)';
                            elements.qrcodeStatus.style.color = 'var(--success-color)';
                            elements.qrcodeLoginBtn.disabled = false;
                            elements.qrcodeLoginBtn.innerHTML = '<i class="fas fa-qrcode"></i> 扫码登录';
                            addLog('大麦网登录成功！', 'success');
                        }
                    } catch {
                        // 继续等待
                    }
                }, 1000);
            } else {
                throw new Error(res?.message || '获取二维码失败');
            }
        } catch (error) {
            elements.qrcodeStatus.innerHTML = `<i class="fas fa-times-circle"></i> <span>获取二维码失败: ${error.message}</span>`;
            elements.qrcodeStatus.style.borderColor = 'var(--error-color)';
            elements.qrcodeStatus.style.color = 'var(--error-color)';
            elements.qrcodeLoginBtn.disabled = false;
            elements.qrcodeLoginBtn.innerHTML = '<i class="fas fa-qrcode"></i> 扫码登录';
            addLog(`获取二维码失败: ${error.message}`, 'error');
        }
    }

    // 测试大麦网登录状态
    async function handleTestDamaiLogin() {
        elements.testLoginBtn.disabled = true;
        elements.testLoginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 检测中...';
        try {
            const res = await api.testLoginStatus();
            if (res && res.logged_in) {
                elements.damaiLoginStatus.textContent = '已登录';
                elements.damaiLoginStatus.className = 'status-value status-running';
                elements.damaiNickname.textContent = res.nickname || '已登录';
                elements.goToMainBtn.disabled = false;
                addLog('大麦网登录状态正常', 'success');
            } else {
                elements.damaiLoginStatus.textContent = '未登录';
                elements.damaiLoginStatus.className = 'status-value status-idle';
                elements.damaiNickname.textContent = '-';
                elements.goToMainBtn.disabled = true;
                addLog('大麦网未登录，请扫码登录', 'warning');
            }
        } catch (error) {
            elements.damaiLoginStatus.textContent = '检测失败';
            elements.damaiLoginStatus.className = 'status-value status-error';
            addLog(`登录状态检测失败: ${error.message}`, 'error');
        } finally {
            elements.testLoginBtn.disabled = false;
            elements.testLoginBtn.innerHTML = '<i class="fas fa-vial"></i> 测试登录状态';
        }
    }

    // 显示/隐藏面板
    function showLoginPanel() {
        elements.loginPanel.style.display = 'block';
        if (elements.damaiLoginPanel) elements.damaiLoginPanel.style.display = 'none';
        elements.mainPanel.style.display = 'none';
        stopMonitoring();
    }

    function showDamaiLoginPanel() {
        elements.loginPanel.style.display = 'none';
        if (elements.damaiLoginPanel) elements.damaiLoginPanel.style.display = 'block';
        elements.mainPanel.style.display = 'none';
        // 加载账号列表
        renderAccountList();
    }

    function showMainPanel() {
        elements.loginPanel.style.display = 'none';
        if (elements.damaiLoginPanel) elements.damaiLoginPanel.style.display = 'none';
        elements.mainPanel.style.display = 'block';
        updateUserStatus(api.user);
        // 加载账号复选框
        renderAccountCheckboxes();
    }

    // 更新用户状态
    function updateUserStatus(user) {
        if (user) {
            elements.userStatus.textContent = user.username;
            elements.connectionStatus.className = 'status-badge status-connected';
            elements.connectionStatus.innerHTML = '<i class="fas fa-plug"></i> 已连接';
        } else {
            elements.userStatus.textContent = '未登录';
            elements.connectionStatus.className = 'status-badge status-disconnected';
            elements.connectionStatus.innerHTML = '<i class="fas fa-plug"></i> 未连接';
        }
    }

    // 检查连接状态
    async function checkConnection() {
        if (!api.isAuthenticated()) return;

        try {
            const startTime = Date.now();
            const health = await api.healthCheck();
            const latency = Date.now() - startTime;

            if (health.status === 'healthy') {
                elements.backendStatus.textContent = '运行正常';
                elements.backendStatus.className = 'status-value status-running';
                elements.latency.textContent = latency;
                elements.latency.className = latency < 100 ? 'status-value status-running' :
                                           latency < 500 ? 'status-value status-warning' :
                                           'status-value status-error';

                // 更新用户信息
                try {
                    const userInfo = await api.getCurrentUser();
                    updateUserStatus(userInfo.data.user);
                } catch (e) {
                    // 忽略
                }
            } else {
                elements.backendStatus.textContent = '服务异常';
                elements.backendStatus.className = 'status-value status-error';
            }
        } catch (error) {
            elements.backendStatus.textContent = '连接失败';
            elements.backendStatus.className = 'status-value status-error';
        }

        // 每30秒检查一次
        setTimeout(checkConnection, 30000);
    }

    // 开始抢票任务
    async function startTicketTask() {
        // 验证输入
        if (!validateTaskInput()) {
            return;
        }

        // 重置状态
        state.currentGroupId = null;
        state.accountTasks = {};
        state.successSoundPlayed = false;
        state.currentTaskStatus = null;
        if (elements.accountTasksSection) {
            elements.accountTasksSection.style.display = 'none';
        }

        // 收集任务数据
        // 解析观演人
        const attendeesText = elements.attendees.value.trim();
        const attendees = [];
        if (attendeesText) {
            const lines = attendeesText.split('\n');
            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed) {
                    const parts = trimmed.split(',');
                    if (parts.length >= 3) {
                        attendees.push({
                            name: parts[0].trim(),
                            id_card: parts[1].trim(),
                            phone: parts[2].trim()
                        });
                    } else {
                        addLog(`观演人格式错误: ${line}，应使用"姓名,身份证,手机号"格式`, 'warning');
                    }
                }
            }
        }

        // 解析演出链接
        const eventId = api.parseEventId(elements.eventId.value.trim());

        // 收集选中的账号ID
        const accountIds = state.selectedAccountIds || [];

        const taskData = {
            eventId: eventId,
            ticketCount: parseInt(elements.ticketCount.value) || 1,
            session: elements.session.value.trim() || null,
            price: elements.price.value.trim() || null,
            retryCount: parseInt(elements.retryCount.value),
            refreshInterval: parseInt(elements.refreshInterval.value),
            startTime: elements.startTime.value || null,
            attendees: attendees,
            accountIds: accountIds
        };

        // 更新UI状态
        elements.startBtn.disabled = true;
        elements.startBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 创建任务中...';
        elements.stopBtn.disabled = false;

        try {
            addLog('正在创建抢票任务...', 'info');

            // 创建任务
            const response = await api.createTask(taskData);

            // 多账号模式：返回 group_id + tasks 数组
            if (response && response.group_id) {
                state.currentGroupId = response.group_id;
                state.accountTasks = {};
                response.tasks.forEach(t => {
                    state.accountTasks[t.account_id] = {
                        taskId: t.task_id,
                        status: t.status,
                        attempt: 0
                    };
                });

                // 显示多账号状态区域
                if (elements.accountTasksSection) {
                    elements.accountTasksSection.style.display = 'block';
                }
                renderAccountTasksStatus();

                addLog(`多账号任务创建成功！组ID: ${response.group_id}，共 ${response.tasks.length} 个账号`, 'success');
                addLog(`演出ID: ${taskData.eventId}, 票数: ${taskData.ticketCount}, 观演人: ${taskData.attendees.length}人`, 'info');

                // 播放开始音效
                if (elements.playSound.checked) {
                    playSound('start');
                }

                // 监控所有任务（使用第一个任务ID建立WebSocket连接）
                const firstTaskId = response.tasks[0]?.task_id;
                if (firstTaskId) {
                    state.currentTaskId = firstTaskId;
                    startMonitoring(firstTaskId);
                }

                elements.startBtn.disabled = true;
                elements.startBtn.innerHTML = '<i class="fas fa-play"></i> 任务进行中';
                elements.stopBtn.disabled = false;

            // 单账号模式（向后兼容）
            } else if (response && response.id) {
                state.currentTaskId = response.id;
                state.currentTaskStatus = response.status;

                updateTaskDisplay(response);
                addLog(`任务创建成功！任务ID: ${response.id}`, 'success');
                addLog(`演出ID: ${taskData.eventId}, 票数: ${taskData.ticketCount}, 观演人: ${taskData.attendees.length}人`, 'info');

                // 播放开始音效
                if (elements.playSound.checked) {
                    playSound('start');
                }

                // 开始监控任务状态
                startMonitoring(response.id);

                // 更新按钮状态
                elements.startBtn.disabled = true;
                elements.startBtn.innerHTML = '<i class="fas fa-play"></i> 任务进行中';
                elements.stopBtn.disabled = false;
            } else {
                throw new Error('创建任务失败：未收到有效响应');
            }
        } catch (error) {
            console.error('创建任务失败:', error);
            addLog(`创建任务失败: ${error.message}`, 'error');

            // 恢复按钮状态
            elements.startBtn.disabled = false;
            elements.startBtn.innerHTML = '<i class="fas fa-play"></i> 开始抢票';
            elements.stopBtn.disabled = true;

            if (error.status === 401) {
                alert('认证失败，请重新登录');
                handleLogout();
            }
        }
    }

    // 停止抢票任务
    async function stopTicketTask() {
        if (!state.currentTaskId && !state.currentGroupId) {
            addLog('没有正在运行的任务', 'warning');
            return;
        }

        const confirmStop = confirm('确定要停止当前抢票任务吗？');
        if (!confirmStop) return;

        try {
            // 多账号模式：取消整个任务组
            if (state.currentGroupId) {
                addLog(`正在停止任务组 ${state.currentGroupId}...`, 'info');
                await api.cancelTaskGroup(state.currentGroupId);
                addLog('任务组已停止', 'success');

                // 更新所有账号状态
                Object.keys(state.accountTasks).forEach(accId => {
                    state.accountTasks[accId].status = 'cancelled';
                });
                renderAccountTasksStatus();
            } else {
                addLog(`正在停止任务 ${state.currentTaskId}...`, 'info');
                await api.cancelTask(state.currentTaskId);
                addLog('任务已停止', 'success');
            }

            state.currentTaskStatus = 'cancelled';
            updateStatusDisplay('已停止');
            stopMonitoring();

            // 更新按钮状态
            elements.startBtn.disabled = false;
            elements.startBtn.innerHTML = '<i class="fas fa-play"></i> 开始抢票';
            elements.stopBtn.disabled = true;
        } catch (error) {
            console.error('停止任务失败:', error);
            addLog(`停止任务失败: ${error.message}`, 'error');
        }
    }

    // 验证任务输入
    function validateTaskInput() {
        const eventInput = elements.eventId.value.trim();
        const ticketCount = parseInt(elements.ticketCount.value);

        if (!eventInput) {
            alert('请输入演出链接或ID');
            elements.eventId.focus();
            return false;
        }

        // 验证能解析出 event_id
        const eventId = api.parseEventId(eventInput);
        if (!eventId) {
            alert('无法解析演出链接，请输入正确的大麦网链接或演出ID');
            elements.eventId.focus();
            return false;
        }

        if (!ticketCount || ticketCount < 1) {
            alert('请输入有效的票数');
            elements.ticketCount.focus();
            return false;
        }

        return true;
    }

    // 开始监控任务状态（WebSocket优先）
    function startMonitoring(taskId) {
        if (!taskId) return;

        state.currentTaskId = taskId;

        // 尝试使用WebSocket
        if (state.useWebSocket && api.getUserId()) {
            startWebSocketMonitoring(taskId);
        } else {
            // 降级到轮询
            addLog('使用轮询模式监控任务状态', 'system');
            startPolling();
        }
    }

    // WebSocket监控
    function startWebSocketMonitoring(taskId) {
        if (!api.getUserId()) {
            addLog('用户未登录，无法使用WebSocket', 'warning');
            startPolling();
            return;
        }

        // 设置WebSocket消息处理
        api.onTaskWebSocketMessage = handleTaskWebSocketMessage;

        // 连接任务WebSocket
        api.connectTaskWebSocket(api.getUserId(), taskId);

        // 设置连接超时检测
        setTimeout(() => {
            if (!state.webSocketConnected && !state.webSocketFallback) {
                addLog('WebSocket连接超时，降级到轮询', 'warning');
                state.webSocketFallback = true;
                startPolling();
            }
        }, 3000);

        addLog('正在通过WebSocket监控任务状态...', 'info');
    }

    // 处理WebSocket消息
    function handleTaskWebSocketMessage(data) {
        const messageType = data.type;

        switch (messageType) {
            case 'subscription_confirmed':
                state.webSocketConnected = true;
                state.webSocketFallback = false;
                addLog(`已订阅任务更新: ${data.task_id}`, 'success');
                break;

            case 'task_status':
                updateTaskFromWebSocket(data);
                break;

            case 'task_log':
                // 实时日志消息（支持账号标签）
                if (data.message) {
                    const accountLabel = data.account_label || null;
                    addLog(data.message, data.level || 'info', data.timestamp, accountLabel);
                    // 检测验证码状态
                    updateCaptchaFromLog(data.message);
                }
                break;

            case 'group_status':
                // 多账号组状态更新
                handleGroupStatus(data);
                break;

            case 'captcha_status':
                // 验证码状态更新
                updateCaptchaDisplay(data.status, data.message);
                break;

            case 'pong':
                // 心跳响应
                break;

            case 'error':
                addLog(`WebSocket错误: ${data.error}`, 'error');
                break;

            default:
                console.log('未知WebSocket消息:', data);
        }
    }

    // 处理多账号组状态
    function handleGroupStatus(data) {
        if (data.overall_status === 'success') {
            const winner = data.winning_account || '';
            const winnerLabel = state.accountTasks[winner]?.label || winner;
            addLog(`[多账号] 抢票成功！成功账号: ${winnerLabel}`, 'success');

            // 更新各账号状态
            if (data.tasks) {
                data.tasks.forEach(t => {
                    if (state.accountTasks[t.account_id]) {
                        state.accountTasks[t.account_id].status = t.status;
                    }
                });
                renderAccountTasksStatus();
            }

            if (elements.playSound.checked) {
                playSound('success');
            }
        } else if (data.overall_status === 'cancelled') {
            addLog('[多账号] 任务组已取消', 'info');
        }
    }

    // 渲染多账号任务状态
    function renderAccountTasksStatus() {
        if (!elements.accountTasksList) return;
        const tasks = state.accountTasks || {};
        const entries = Object.entries(tasks);

        if (entries.length === 0) {
            elements.accountTasksList.innerHTML = '<div class="account-empty">暂无多账号任务</div>';
            return;
        }

        elements.accountTasksList.innerHTML = entries.map(([accId, info]) => {
            const statusClass = `status-${info.status || 'running'}`;
            const statusText = {
                'running': '运行中', 'waiting': '等待中', 'success': '成功',
                'failed': '失败', 'cancelled': '已取消', 'error': '异常'
            }[info.status] || info.status;
            const label = info.label || accId;
            return `
                <div class="account-task-card ${statusClass}">
                    <span class="account-task-label">${label}</span>
                    <span class="account-task-status">${statusText}</span>
                    <span class="account-task-attempt">尝试: ${info.attempt || 0}</span>
                </div>
            `;
        }).join('');
    }

    // 从日志消息中检测验证码状态
    function updateCaptchaFromLog(message) {
        if (!elements.captchaStatus) return;
        const msg = message.toLowerCase();
        if (msg.includes('验证码') || msg.includes('captcha')) {
            if (msg.includes('识别成功') || msg.includes('通过')) {
                updateCaptchaDisplay('success', '验证码识别成功');
            } else if (msg.includes('识别失败') || msg.includes('错误')) {
                updateCaptchaDisplay('fail', '验证码识别失败');
            } else if (msg.includes('识别中') || msg.includes('正在')) {
                updateCaptchaDisplay('processing', '正在识别验证码...');
            }
        }
    }

    // 更新验证码状态显示
    function updateCaptchaDisplay(status, message) {
        if (!elements.captchaStatus) return;
        elements.captchaStatus.textContent = message || status;
        elements.captchaStatus.className = 'status-value';
        switch (status) {
            case 'processing':
                elements.captchaStatus.classList.add('captcha-processing');
                break;
            case 'success':
                elements.captchaStatus.classList.add('captcha-success');
                break;
            case 'fail':
                elements.captchaStatus.classList.add('captcha-fail');
                break;
            default:
                elements.captchaStatus.classList.add('status-idle');
        }
    }

    // 从WebSocket更新任务状态
    function updateTaskFromWebSocket(data) {
        const taskId = data.task_id;
        const accountId = data.account_id;

        // 多账号模式：更新对应账号的状态
        if (accountId && state.accountTasks[accountId]) {
            state.accountTasks[accountId].status = data.status;
            if (data.attempt !== undefined) {
                state.accountTasks[accountId].attempt = data.attempt;
            }
            renderAccountTasksStatus();
        }

        // 兼容：非多账号模式下，只处理当前任务
        if (!accountId && taskId !== state.currentTaskId) return;

        // 创建模拟任务对象
        const task = {
            id: taskId,
            status: data.status,
            current_attempt: data.attempt || data.current_attempt,
            max_attempts: data.max_attempts,
            progress: data.progress || 0
        };

        updateTaskDisplay(task);

        // 更新尝试次数
        if (task.current_attempt !== undefined && elements.attemptCount) {
            elements.attemptCount.textContent = task.current_attempt;
        }

        // 检查状态变化
        if (data.status !== state.currentTaskStatus) {
            state.currentTaskStatus = data.status;
            handleTaskStatusChange(task);
        }

        // 检查是否成功
        if (data.status === 'success' && !state.successSoundPlayed) {
            state.successSoundPlayed = true;
            showSuccessModal(task);
            stopMonitoring();
        }

        // 检查是否失败或超时
        if (['failed', 'timeout', 'cancelled'].includes(data.status)) {
            // 多账号模式下，只有当所有任务都结束时才停止监控
            if (state.currentGroupId) {
                const allDone = Object.values(state.accountTasks).every(
                    t => ['success', 'failed', 'cancelled', 'error'].includes(t.status)
                );
                if (allDone) {
                    stopMonitoring();
                    elements.startBtn.disabled = false;
                    elements.startBtn.innerHTML = '<i class="fas fa-play"></i> 开始抢票';
                    elements.stopBtn.disabled = true;
                }
            } else {
                stopMonitoring();
                elements.startBtn.disabled = false;
                elements.startBtn.innerHTML = '<i class="fas fa-play"></i> 开始抢票';
                elements.stopBtn.disabled = true;
            }
        }
    }

    // 停止所有监控
    function stopMonitoring() {
        stopWebSocketMonitoring();
        stopPolling();
    }

    // 停止WebSocket监控
    function stopWebSocketMonitoring() {
        if (api.taskWsConnected) {
            api.closeTaskWebSocket();
        }
        state.webSocketConnected = false;
        state.webSocketFallback = false;
        api.onTaskWebSocketMessage = null;
    }

    // 轮询任务状态（降级模式）
    function startPolling() {
        if (state.isPolling) return;

        state.isPolling = true;
        const interval = parseInt(elements.refreshInterval.value) || 200;

        addLog(`开始轮询任务状态，间隔: ${interval}ms`, 'info');

        // 立即执行第一次轮询
        pollTaskStatus();

        // 设置定时器
        state.pollInterval = setInterval(pollTaskStatus, interval);
    }

    function stopPolling() {
        if (state.pollInterval) {
            clearInterval(state.pollInterval);
            state.pollInterval = null;
        }
        state.isPolling = false;
        addLog('已停止轮询', 'system');
    }

    async function pollTaskStatus() {
        if (!state.currentTaskId) return;

        try {
            // 获取任务详情
            const task = await api.getTask(state.currentTaskId);
            updateTaskDisplay(task);

            // 获取任务日志
            const logs = await api.getTaskLogs(state.currentTaskId, 20);
            updateTaskLogs(logs);

            // 检查任务状态变化
            if (task.status !== state.currentTaskStatus) {
                state.currentTaskStatus = task.status;
                handleTaskStatusChange(task);
            }

            // 检查是否成功
            if (task.status === 'success' && !state.successSoundPlayed) {
                state.successSoundPlayed = true;
                showSuccessModal(task);
                stopMonitoring();
            }

            // 检查是否失败或超时
            if (['failed', 'timeout', 'cancelled'].includes(task.status)) {
                stopMonitoring();
                elements.startBtn.disabled = false;
                elements.startBtn.innerHTML = '<i class="fas fa-play"></i> 开始抢票';
                elements.stopBtn.disabled = true;
            }

        } catch (error) {
            console.error('轮询失败:', error);
            if (error.status === 404) {
                addLog('任务不存在或已被删除', 'error');
                stopMonitoring();
            }
        }
    }

    // 更新任务显示
    function updateTaskDisplay(task) {
        if (!task) return;

        elements.taskId.textContent = task.id;
        elements.currentStatus.textContent = task.status;
        elements.currentStatus.className = `status-value status-${task.status}`;

        // 更新尝试次数和成功次数
        elements.attemptCount.textContent = task.current_attempt || 0;
        elements.successCount.textContent = task.success_count || 0;

        // 更新最后更新时间
        state.lastUpdate = new Date();
        elements.lastUpdate.textContent = formatTime(state.lastUpdate);
    }

    // 更新任务日志
    function updateTaskLogs(logs) {
        if (!Array.isArray(logs)) return;

        // 只添加新的日志
        for (const log of logs) {
            const logId = log.id || `${log.timestamp}_${log.message}`;
            if (!state.logs.some(l => l.id === logId)) {
                addLog(log.message, log.level?.toLowerCase() || 'info', log.timestamp);
                state.logs.push({ id: logId, ...log });
            }
        }

        // 限制日志数量
        if (state.logs.length > state.maxLogs) {
            state.logs = state.logs.slice(-state.maxLogs);
            // 重新渲染？暂时不处理
        }

        // 更新日志计数
        elements.logCount.textContent = `日志: ${state.logs.length} 条`;
        elements.totalLogs.textContent = state.logs.length;

        if (state.logs.length > 0) {
            const lastLog = state.logs[state.logs.length - 1];
            elements.lastLogTime.textContent = `最后日志: ${formatTime(new Date(lastLog.timestamp))}`;
        }
    }

    // 处理任务状态变化
    function handleTaskStatusChange(task) {
        const statusMap = {
            'pending': '等待中',
            'running': '运行中',
            'success': '成功',
            'failed': '失败',
            'timeout': '超时',
            'cancelled': '已取消'
        };

        const statusText = statusMap[task.status] || task.status;
        addLog(`任务状态变更为: ${statusText}`, 'info');

        if (task.status === 'success') {
            addLog('🎉 抢票成功！请尽快完成支付！', 'success');
            if (elements.playSound.checked) {
                playSound('success');
            }
        } else if (task.status === 'failed') {
            addLog(`任务失败: ${task.error_message || '未知错误'}`, 'error');
            if (elements.playSound.checked) {
                playSound('error');
            }
        }
    }

    // 添加日志
    function addLog(message, level = 'info', timestamp = null, accountLabel = null) {
        const time = timestamp ? new Date(timestamp) : new Date();
        const timeStr = formatTime(time);
        const levelClass = level.toLowerCase();

        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${levelClass}`;

        if (accountLabel) {
            const tag = document.createElement('span');
            tag.className = 'log-account-tag';
            tag.textContent = accountLabel;
            logEntry.appendChild(tag);
            logEntry.appendChild(document.createTextNode(`${timeStr} ${message}`));
        } else {
            logEntry.textContent = `${timeStr} ${message}`;
        }

        elements.logContainer.appendChild(logEntry);

        // 自动滚动
        if (elements.autoScroll.checked) {
            logEntry.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        // 更新日志计数
        elements.totalLogs.textContent = parseInt(elements.totalLogs.textContent) + 1;
    }

    // 清空日志
    function clearLogs() {
        elements.logContainer.innerHTML = '';
        state.logs = [];
        addLog('日志已清空', 'system');
    }

    // 显示成功模态框
    function showSuccessModal(task) {
        const config = task.config || {};
        elements.successConcert.textContent = config.concert_name || '未知';
        elements.successSession.textContent = task.success_session || config.sessions?.[0] || '未知';
        elements.successPrice.textContent = task.success_price || config.prices?.[0] || '未知';

        if (task.order_url) {
            elements.successOrderLink.href = task.order_url;
            elements.successOrderLink.style.display = 'inline';
        } else {
            elements.successOrderLink.style.display = 'none';
        }

        elements.successModal.style.display = 'flex';
        playSuccessSound();
    }

    function hideSuccessModal() {
        elements.successModal.style.display = 'none';
    }

    // 播放音效
    function playSound(type) {
        if (!elements.playSound.checked) return;

        try {
            const audio = elements[`${type}Sound`];
            if (audio) {
                audio.currentTime = 0;
                audio.play().catch(e => console.warn('播放音效失败:', e));
            }
        } catch (error) {
            console.warn('播放音效失败:', error);
        }
    }

    function playSuccessSound() {
        playSound('success');
    }

    // 复制订单链接
    function copyOrderLink() {
        const link = elements.successOrderLink.href;
        if (link && link !== '#') {
            navigator.clipboard.writeText(link).then(() => {
                alert('订单链接已复制到剪贴板');
            }).catch(err => {
                console.error('复制失败:', err);
                alert('复制失败，请手动复制链接');
            });
        }
    }

    // 更新任务摘要（占位符）
    function updateTaskSummary() {
        // 可以在这里实现实时预览
    }

    // 更新状态显示
    function updateStatusDisplay(status) {
        elements.currentStatus.textContent = status;
        elements.currentStatus.className = `status-value status-${status.toLowerCase()}`;
    }

    // 更新时间显示
    function updateCurrentTime() {
        const now = new Date();
        elements.currentTime.textContent = now.toLocaleTimeString('zh-CN');
    }

    // 工具函数
    function formatTime(date) {
        if (!(date instanceof Date)) {
            date = new Date(date);
        }
        return date.toLocaleTimeString('zh-CN', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    // 启动应用
    init();
});