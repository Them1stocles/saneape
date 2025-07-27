// Enhanced SaneApe.com Application with Dynamic UI and Rate Limiting
class SaneApeApp {
    constructor() {
        this.form = document.getElementById('stockForm');
        this.tickerInput = document.getElementById('ticker');
        this.maxBrainCheck = document.getElementById('maximumBrain');
        this.analyzeBtn = document.getElementById('analyzeBtn');
        this.loadingState = document.getElementById('loadingState');
        this.alertContainer = document.getElementById('alertContainer');
        this.resultsSection = document.getElementById('resultsSection');
        
        this.remainingRequests = null;
        this.isAnalyzing = false;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadUserStatus();
        
        // Auto-refresh user status every 30 seconds
        setInterval(() => this.loadUserStatus(), 30000);
    }
    
    setupEventListeners() {
        // Form submission
        this.form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        
        // Real-time input validation
        this.tickerInput.addEventListener('input', () => this.validateInput());
        
        // Maximum Brain checkbox change
        this.maxBrainCheck.addEventListener('change', () => this.updateButtonState());
        
        // Enter key support
        this.tickerInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !this.isAnalyzing) {
                e.preventDefault();
                this.handleFormSubmit(e);
            }
        });
    }
    
    async loadUserStatus() {
        try {
            const response = await fetch('/api/user-status');
            const data = await response.json();
            
            if (data.success) {
                this.remainingRequests = data.data;
                this.updateRateLimitDisplay();
                this.updateButtonState();
            }
        } catch (error) {
            console.error('Error loading user status:', error);
            // Provide fallback values to prevent UI breaking
            this.remainingRequests = {
                standard_remaining: 2,
                brain_remaining: 1,
                total_used: 0
            };
            this.updateRateLimitDisplay();
            this.updateButtonState();
        }
    }
    
    updateRateLimitDisplay() {
        if (!this.remainingRequests) return;
        
        const standardEl = document.getElementById('standardRemaining');
        const brainEl = document.getElementById('brainRemaining');
        
        if (standardEl) {
            const remaining = this.remainingRequests.standard_remaining || 0;
            standardEl.textContent = `${remaining} remaining`;
            standardEl.className = `h5 mb-1 ${remaining === 0 ? 'text-danger' : remaining === 1 ? 'text-warning' : 'text-success'}`;
        }
        
        if (brainEl) {
            const remaining = this.remainingRequests.brain_remaining || 0;
            brainEl.textContent = `${remaining} remaining`;
            brainEl.className = `h5 mb-1 ${remaining === 0 ? 'text-danger' : 'text-success'}`;
        }
    }
    
    validateInput() {
        const ticker = this.tickerInput.value.trim();
        const isValid = ticker.length > 0 && ticker.length <= 5 && /^[A-Za-z]+$/.test(ticker);
        
        // Update input styling
        if (ticker.length > 0) {
            this.tickerInput.classList.toggle('is-valid', isValid);
            this.tickerInput.classList.toggle('is-invalid', !isValid);
        } else {
            this.tickerInput.classList.remove('is-valid', 'is-invalid');
        }
        
        this.updateButtonState();
        return isValid;
    }
    
    updateButtonState() {
        if (!this.remainingRequests) return;
        
        const ticker = this.tickerInput.value.trim();
        const isValidInput = ticker.length > 0 && ticker.length <= 5 && /^[A-Za-z]+$/.test(ticker);
        const isMaxBrain = this.maxBrainCheck.checked;
        
        const hasStandardRemaining = this.remainingRequests.standard_remaining > 0;
        const hasBrainRemaining = this.remainingRequests.brain_remaining > 0;
        
        let canAnalyze = isValidInput && !this.isAnalyzing;
        let buttonText = 'Analyze Stock';
        let buttonClass = 'btn btn-primary btn-lg w-100';
        
        if (isMaxBrain) {
            canAnalyze = canAnalyze && hasBrainRemaining;
            if (!hasBrainRemaining) {
                buttonText = 'Maximum Brain Limit Reached';
                buttonClass = 'btn btn-secondary btn-lg w-100';
            }
        } else {
            canAnalyze = canAnalyze && hasStandardRemaining;
            if (!hasStandardRemaining) {
                buttonText = 'Daily Limit Reached';
                buttonClass = 'btn btn-secondary btn-lg w-100';
            }
        }
        
        if (this.isAnalyzing) {
            buttonText = 'Analyzing...';
            buttonClass = 'btn btn-warning btn-lg w-100';
        }
        
        this.analyzeBtn.disabled = !canAnalyze;
        this.analyzeBtn.textContent = buttonText;
        this.analyzeBtn.className = buttonClass;
    }
    
    async handleFormSubmit(e) {
        e.preventDefault();
        
        if (this.isAnalyzing || !this.validateInput()) return;
        
        const ticker = this.tickerInput.value.trim().toUpperCase();
        const maximumBrain = this.maxBrainCheck.checked;
        
        this.setAnalyzingState(true);
        this.clearAlerts();
        this.hideResults();
        
        try {
            const formData = new FormData();
            formData.append('ticker', ticker);
            formData.append('maximum_brain', maximumBrain.toString());
            
            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.displayResults(data);
                this.showAlert('Analysis completed successfully!', 'success');
                
                // Refresh user status to update remaining requests
                await this.loadUserStatus();
            } else {
                this.handleError(data.error, data.type);
            }
            
        } catch (error) {
            console.error('Analysis error:', error);
            this.showAlert('Network error. Please check your connection and try again.', 'danger');
        } finally {
            this.setAnalyzingState(false);
        }
    }
    
    setAnalyzingState(analyzing) {
        this.isAnalyzing = analyzing;
        
        if (analyzing) {
            this.loadingState.classList.remove('d-none');
            this.form.style.opacity = '0.7';
        } else {
            this.loadingState.classList.add('d-none');
            this.form.style.opacity = '1';
        }
        
        this.updateButtonState();
    }
    
    displayResults(data) {
        // Update stock information
        document.getElementById('stockTitle').textContent = 
            `${data.ticker} - ${data.company_name}`;
        document.getElementById('stockPrice').textContent = 
            `Current Price: $${parseFloat(data.current_price).toFixed(2)}`;
        
        // Update recommendation badge
        const recBadge = document.getElementById('recommendationBadge');
        const recommendation = data.recommendation.toLowerCase();
        
        recBadge.textContent = data.recommendation;
        recBadge.className = `badge fs-4 p-3 mb-3 ${
            recommendation.includes('buy') ? 'bg-success' : 'bg-danger'
        }`;
        
        // Update confidence badge
        const confBadge = document.getElementById('confidenceBadge');
        confBadge.textContent = data.confidence;
        confBadge.className = `badge ${this.getConfidenceClass(data.confidence)}`;
        
        // Update explanation
        document.getElementById('overallExplanation').textContent = 
            data.overall_explanation;
        
        // Update technical analysis details
        this.displayTechnicalAnalysis(data.analysis_details);
        
        // Show results
        this.resultsSection.classList.remove('d-none');
        this.resultsSection.scrollIntoView({ behavior: 'smooth' });
        
        // Re-initialize feather icons for new content
        feather.replace();
    }
    
    displayTechnicalAnalysis(details) {
        const container = document.getElementById('technicalAnalysisList');
        
        if (!details || details.length === 0) {
            container.innerHTML = '<p class="text-muted">No detailed analysis available.</p>';
            return;
        }
        
        const html = details.map(item => `
            <div class="border-start border-3 border-primary ps-3 mb-3">
                <h6 class="mb-1">${item.indicator}</h6>
                <p class="mb-1">${item.analysis}</p>
                <small class="text-muted">Signal: ${item.signal}</small>
            </div>
        `).join('');
        
        container.innerHTML = html;
    }
    
    getConfidenceClass(confidence) {
        const conf = confidence.toLowerCase();
        if (conf.includes('high')) return 'bg-success';
        if (conf.includes('medium')) return 'bg-warning';
        return 'bg-secondary';
    }
    
    handleError(error, type) {
        let alertType = 'danger';
        let message = error;
        
        if (type === 'rate_limit') {
            alertType = 'warning';
            message = `${error} Your limits will reset at midnight UTC.`;
        } else if (type === 'validation') {
            alertType = 'info';
        }
        
        this.showAlert(message, alertType);
        
        // Refresh user status after rate limit errors
        if (type === 'rate_limit') {
            this.loadUserStatus();
        }
    }
    
    showAlert(message, type = 'info') {
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                <i data-feather="${this.getAlertIcon(type)}" class="me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        this.alertContainer.innerHTML = alertHtml;
        feather.replace();
        
        // Auto-dismiss success alerts after 5 seconds
        if (type === 'success') {
            setTimeout(() => this.clearAlerts(), 5000);
        }
    }
    
    getAlertIcon(type) {
        const icons = {
            success: 'check-circle',
            danger: 'alert-circle',
            warning: 'alert-triangle',
            info: 'info'
        };
        return icons[type] || 'info';
    }
    
    clearAlerts() {
        this.alertContainer.innerHTML = '';
    }
    
    hideResults() {
        this.resultsSection.classList.add('d-none');
    }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new SaneApeApp();
});

// Global error handling
window.addEventListener('error', (e) => {
    console.error('Global error:', e.error);
});

window.addEventListener('unhandledrejection', (e) => {
    console.error('Unhandled promise rejection:', e.reason);
});