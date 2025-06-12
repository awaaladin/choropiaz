// Initialize the Banking API
const bankingAPI = new BankingAPI('https://gax-2.onrender.com');

// Dashboard functionality
class BankingDashboard {
    constructor() {
        this.initializeElements();
        this.attachEventListeners();
        this.loadDashboard();
    }

    initializeElements() {
        this.balanceElement = document.getElementById('balance');
        this.transactionsList = document.getElementById('transactions');
        this.transferForm = document.getElementById('transfer-form');
        this.billPaymentForm = document.getElementById('bill-payment-form');
        this.notificationArea = document.getElementById('notifications');
    }

    attachEventListeners() {
        // Transfer money form
        this.transferForm?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            try {
                const result = await bankingAPI.transfer({
                    recipient: formData.get('recipient'),
                    amount: formData.get('amount'),
                    description: formData.get('description')
                });
                if (result.success) {
                    this.showSuccess('Transfer successful!');
                    this.loadDashboard(); // Refresh dashboard
                }
            } catch (error) {
                this.showError(error.message);
            }
        });

        // Bill payment form
        this.billPaymentForm?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            try {
                const result = await bankingAPI.payBill({
                    billId: formData.get('billId'),
                    amount: formData.get('amount')
                });
                if (result.success) {
                    this.showSuccess('Bill payment successful!');
                    this.loadDashboard(); // Refresh dashboard
                }
            } catch (error) {
                this.showError(error.message);
            }
        });
    }

    async loadDashboard() {
        try {
            // Load account balance
            const balance = await bankingAPI.getBalance();
            if (this.balanceElement) {
                this.balanceElement.textContent = `$${balance.amount.toFixed(2)}`;
            }

            // Load recent transactions
            const transactions = await bankingAPI.getTransactions();
            this.displayTransactions(transactions);

            // Load notifications
            const notifications = await bankingAPI.getNotifications();
            this.displayNotifications(notifications);

        } catch (error) {
            this.showError('Error loading dashboard data');
            console.error(error);
        }
    }

    displayTransactions(transactions) {
        if (!this.transactionsList) return;
        
        this.transactionsList.innerHTML = transactions.map(transaction => `
            <div class="transaction-item">
                <div class="transaction-info">
                    <span class="transaction-type">${transaction.type}</span>
                    <span class="transaction-amount ${transaction.amount < 0 ? 'debit' : 'credit'}">
                        ${transaction.amount < 0 ? '-' : '+'}$${Math.abs(transaction.amount).toFixed(2)}
                    </span>
                </div>
                <div class="transaction-details">
                    <span class="transaction-date">${new Date(transaction.date).toLocaleDateString()}</span>
                    <span class="transaction-description">${transaction.description}</span>
                </div>
            </div>
        `).join('');
    }

    displayNotifications(notifications) {
        if (!this.notificationArea) return;

        this.notificationArea.innerHTML = notifications.map(notification => `
            <div class="notification-item ${notification.type}">
                <span class="notification-message">${notification.message}</span>
                <span class="notification-date">${new Date(notification.date).toLocaleDateString()}</span>
            </div>
        `).join('');
    }

    showSuccess(message) {
        // Implementation of success message display
        const alert = document.createElement('div');
        alert.className = 'alert alert-success';
        alert.textContent = message;
        document.body.appendChild(alert);
        setTimeout(() => alert.remove(), 3000);
    }

    showError(message) {
        // Implementation of error message display
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger';
        alert.textContent = message;
        document.body.appendChild(alert);
        setTimeout(() => alert.remove(), 3000);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new BankingDashboard();
});
