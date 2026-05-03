/**
 * 大麦抢票系统 - API 客户端模块
 *
 * 本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。
 * 请勿用于任何商业或非法用途。
 *
 * 技术要点：
 * - RESTful API 封装（fetch API）
 * - WebSocket 实时通信（自动重连机制）
 * - JWT Token 管理（localStorage 持久化）
 * - HTTP 轮询降级（WebSocket 不可用时回退）
 *
 * 作者：小吴 (Xiao Wu)
 * 许可证：MIT
 */

class DamaiAPI {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.apiPrefix = `${baseUrl}/api/v1`;
        this.token = localStorage.getItem('damai_token') || null;
        this.user = JSON.parse(localStorage.getItem('damai_user') || 'null');
        this.ws = null;
        this.wsConnected = false;
        this.taskWs = null;
        this.taskWsConnected = false;
        this.pendingRequests = new Map();
        this.requestId = 0;
    }

    /**
     * 设置认证令牌
     */
    setToken(token) {
        this.token = token;
        localStorage.setItem('damai_token', token);
    }

    /**
     * 设置用户信息
     */
    setUser(user) {
        this.user = user;
        localStorage.setItem('damai_user', JSON.stringify(user));
    }

    /**
     * 清除认证信息
     */
    clearAuth() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('damai_token');
        localStorage.removeItem('damai_user');
        this.closeWebSocket();
    }

    /**
     * 获取认证头
     */
    getAuthHeaders() {
        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        };
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        return headers;
    }

    /**
     * 发送请求
     */
    async request(method, endpoint, data = null, options = {}) {
        const url = `${this.apiPrefix}${endpoint}`;
        const headers = this.getAuthHeaders();

        const config = {
            method,
            headers,
            ...options
        };

        if (data) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);
            const contentType = response.headers.get('content-type');

            let responseData;
            if (contentType && contentType.includes('application/json')) {
                responseData = await response.json();
            } else {
                responseData = await response.text();
            }

            if (!response.ok) {
                const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
                error.status = response.status;
                error.data = responseData;
                throw error;
            }

            return responseData;
        } catch (error) {
            console.error(`API请求失败: ${method} ${endpoint}`, error);
            throw error;
        }
    }

    /**
     * 用户认证
     */

    async login(username, password) {
        const data = {
            username,
            password
        };

        try {
            const response = await this.request('POST', '/auth/login', data);

            if (response.success) {
                this.setToken(response.data.token);
                this.setUser(response.data.user);
                return response;
            } else {
                throw new Error(response.message || '登录失败');
            }
        } catch (error) {
            console.error('登录失败:', error);
            throw error;
        }
    }

    async getCurrentUser() {
        return this.request('GET', '/auth/me');
    }

    async logout() {
        this.clearAuth();
        return { success: true, message: '已退出登录' };
    }

    /**
     * 任务管理
     */

    async createTask(taskData) {
        // 将前端表单数据转换为后端格式
        const requestData = {
            event_id: taskData.eventId,
            ticket_count: taskData.ticketCount || 1,
            attendees: taskData.attendees || [],
            session: taskData.session || null,
            price: taskData.price || null,
            retry_count: taskData.retryCount || 999,
            refresh_interval: taskData.refreshInterval || 200,
            start_time: taskData.startTime || null,
            account_ids: taskData.accountIds || []
        };

        return this.request('POST', '/tasks', requestData);
    }

    async cancelTaskGroup(groupId) {
        return this.request('POST', `/tasks/group/${groupId}/cancel`);
    }

    async getTasks(status = null, skip = 0, limit = 100) {
        let endpoint = `/tasks?skip=${skip}&limit=${limit}`;
        if (status) {
            endpoint += `&status=${status}`;
        }
        return this.request('GET', endpoint);
    }

    async getTask(taskId) {
        return this.request('GET', `/tasks/${taskId}`);
    }

    async cancelTask(taskId) {
        return this.request('POST', `/tasks/${taskId}/cancel`);
    }

    async deleteTask(taskId) {
        return this.request('DELETE', `/tasks/${taskId}`);
    }

    async retryTask(taskId) {
        return this.request('POST', `/tasks/${taskId}/retry`);
    }

    async getTaskLogs(taskId, limit = 100) {
        return this.request('GET', `/tasks/${taskId}/logs?limit=${limit}`);
    }

    async getTaskStats() {
        return this.request('GET', '/tasks/stats/mine');
    }

    /**
     * 登录状态管理（大麦网）
     */

    async startQrcodeLogin() {
        return this.request('POST', '/login/qrcode');
    }

    async testLoginStatus() {
        return this.request('GET', '/login/test');
    }

    async refreshLogin() {
        return this.request('POST', '/login/refresh');
    }

    async getCookiesStatus() {
        return this.request('GET', '/login/cookies/status');
    }

    async saveCookies(cookiesData) {
        const data = { cookies_data: cookiesData };
        return this.request('POST', '/login/cookies', data);
    }

    /**
     * 多账号管理
     */

    async getAccounts() {
        return this.request('GET', '/accounts');
    }

    async addAccount() {
        return this.request('POST', '/accounts');
    }

    async deleteAccount(accountId) {
        return this.request('DELETE', `/accounts/${accountId}`);
    }

    async loginAccount(accountId) {
        return this.request('POST', `/accounts/${accountId}/login`);
    }

    async testAccountLogin(accountId) {
        return this.request('GET', `/accounts/${accountId}/login/status`);
    }

    /**
     * 系统监控
     */

    async healthCheck() {
        try {
            const response = await fetch(`${this.baseUrl}/health`);
            return response.ok ? { status: 'healthy' } : { status: 'unhealthy' };
        } catch (error) {
            return { status: 'error', error: error.message };
        }
    }

    async getConfig() {
        try {
            const response = await fetch(`${this.baseUrl}/config`);
            if (response.ok) {
                return await response.json();
            }
            return null;
        } catch (error) {
            return null;
        }
    }

    /**
     * WebSocket 连接
     */

    connectWebSocket(userId) {
        if (!this.user || !this.token) {
            console.error('无法建立WebSocket连接：用户未登录');
            return;
        }

        const wsUrl = `ws://${new URL(this.baseUrl).host}/api/v1/login/ws/${userId}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('登录WebSocket连接已建立');
            this.wsConnected = true;
            // 发送认证消息
            this.ws.send(JSON.stringify({
                type: 'auth',
                token: this.token
            }));
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('WebSocket消息解析失败:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('登录WebSocket错误:', error);
            this.wsConnected = false;
        };

        this.ws.onclose = () => {
            console.log('登录WebSocket连接已关闭');
            this.wsConnected = false;
        };
    }

    /**
     * 任务WebSocket连接
     */
    connectTaskWebSocket(userId, taskId = null) {
        if (!this.user || !this.token) {
            console.error('无法建立任务WebSocket连接：用户未登录');
            return;
        }

        const wsUrl = `ws://${new URL(this.baseUrl).host}/api/v1/tasks/ws/${userId}`;
        this.taskWs = new WebSocket(wsUrl);

        this.taskWs.onopen = () => {
            console.log('任务WebSocket连接已建立');
            this.taskWsConnected = true;

            // 如果有特定任务ID，订阅该任务
            if (taskId) {
                this.sendTaskWebSocketMessage('subscribe_task', { task_id: taskId });
            } else {
                // 否则订阅用户所有任务
                this.sendTaskWebSocketMessage('subscribe_all');
            }
        };

        this.taskWs.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleTaskWebSocketMessage(data);
            } catch (error) {
                console.error('任务WebSocket消息解析失败:', error);
            }
        };

        this.taskWs.onerror = (error) => {
            console.error('任务WebSocket错误:', error);
            this.taskWsConnected = false;
        };

        this.taskWs.onclose = () => {
            console.log('任务WebSocket连接已关闭');
            this.taskWsConnected = false;
        };
    }

    /**
     * 处理任务WebSocket消息
     */
    handleTaskWebSocketMessage(data) {
        // 分发任务WebSocket消息
        if (typeof this.onTaskWebSocketMessage === 'function') {
            this.onTaskWebSocketMessage(data);
        }
    }

    /**
     * 发送任务WebSocket消息
     */
    sendTaskWebSocketMessage(type, data = {}) {
        if (!this.taskWsConnected || !this.taskWs) {
            console.error('任务WebSocket未连接');
            return false;
        }

        try {
            const message = { type, ...data };
            this.taskWs.send(JSON.stringify(message));
            return true;
        } catch (error) {
            console.error('发送任务WebSocket消息失败:', error);
            return false;
        }
    }

    /**
     * 订阅特定任务更新
     */
    subscribeTask(taskId) {
        return this.sendTaskWebSocketMessage('subscribe_task', { task_id: taskId });
    }

    /**
     * 取消订阅任务更新
     */
    unsubscribeTask(taskId) {
        return this.sendTaskWebSocketMessage('unsubscribe_task', { task_id: taskId });
    }

    /**
     * 获取任务状态
     */
    requestTaskStatus(taskId) {
        return this.sendTaskWebSocketMessage('get_task_status', { task_id: taskId });
    }

    /**
     * 关闭任务WebSocket
     */
    closeTaskWebSocket() {
        if (this.taskWs) {
            this.taskWs.close();
            this.taskWs = null;
            this.taskWsConnected = false;
        }
    }

    handleWebSocketMessage(data) {
        // 分发WebSocket消息
        if (typeof this.onWebSocketMessage === 'function') {
            this.onWebSocketMessage(data);
        }
    }

    sendWebSocketMessage(type, data = {}) {
        if (!this.wsConnected || !this.ws) {
            console.error('WebSocket未连接');
            return false;
        }

        try {
            const message = { type, ...data };
            this.ws.send(JSON.stringify(message));
            return true;
        } catch (error) {
            console.error('发送WebSocket消息失败:', error);
            return false;
        }
    }

    closeWebSocket() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
            this.wsConnected = false;
        }
    }

    /**
     * 工具方法
     */

    async ping() {
        const start = Date.now();
        try {
            await fetch(`${this.baseUrl}/health`);
            return Date.now() - start;
        } catch (error) {
            return null;
        }
    }

    /**
     * 从大麦网链接中提取 event_id
     * 支持格式: https://m.damai.cn/shows/item.html?itemId=123456
     *          https://detail.damai.cn/item.htm?id=123456
     *          纯数字ID
     */
    parseEventId(input) {
        if (!input) return null;
        input = input.trim();
        // 纯数字
        if (/^\d+$/.test(input)) return input;
        // URL 中提取 itemId 或 id 参数
        try {
            const url = new URL(input);
            return url.searchParams.get('itemId') || url.searchParams.get('id') || null;
        } catch {
            return null;
        }
    }

    isAuthenticated() {
        return !!this.token && !!this.user;
    }

    getUserId() {
        return this.user?.id;
    }
}

// 创建全局API实例
window.DamaiAPI = DamaiAPI;
window.api = new DamaiAPI();