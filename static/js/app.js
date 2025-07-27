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
        
        // Validate critical elements exist
        if (!this.loadingState) {
            console.error('loadingState element not found');
            this.loadingState = { classList: { add: () => {}, remove: () => {} } }; // Fallback
        }
        if (!this.form) {
            console.error('stockForm element not found');
            return;
        }
        if (!this.analyzeBtn) {
            console.error('analyzeBtn element not found');
            return;
        }
        
        this.remainingRequests = null;
        this.isAnalyzing = false;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadUserStatus();
        this.loadRecentAnalyses();
        
        // Auto-refresh user status every 30 seconds
        setInterval(() => this.loadUserStatus(), 30000);
        
        // Auto-refresh recent analyses every 2 minutes
        setInterval(() => this.loadRecentAnalyses(), 120000);
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
            return Promise.resolve(); // Prevent unhandled promise rejection
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
            return Promise.resolve(); // Prevent unhandled promise rejection
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
        // Parse the current price properly - handle both "$123.45" and "123.45" formats
        let priceValue = data.current_price;
        let formattedPrice = "Price unavailable";
        
        if (priceValue && priceValue !== "Price unavailable" && priceValue !== "N/A") {
            // Remove $ symbol if present and parse as float
            const numericPrice = parseFloat(priceValue.toString().replace('$', ''));
            if (!isNaN(numericPrice)) {
                formattedPrice = `$${numericPrice.toFixed(2)}`;
            }
        }
        
        document.getElementById('stockPrice').innerHTML = 
            `Current Price: <strong>${formattedPrice}</strong> <small class="text-success"><i data-feather="refresh-cw" style="width: 12px; height: 12px;"></i> Live</small>`;
        
        // Update recommendation badge
        const recBadge = document.getElementById('recommendationBadge');
        const recommendation = data.recommendation.toLowerCase();
        
        // Standardize the text for consistency
        let displayText;
        let badgeClass;
        if (recommendation.includes("don't buy") || recommendation.includes("no,") || recommendation.includes("no buy")) {
            displayText = "No Buy";
            badgeClass = 'bg-danger';
        } else if (recommendation.includes("yes,") || (recommendation.includes('buy') && !recommendation.includes("don't"))) {
            displayText = "Buy";
            badgeClass = 'bg-success';
        } else {
            displayText = data.recommendation;
            badgeClass = 'bg-secondary';
        }
        
        recBadge.textContent = displayText;
        recBadge.className = `badge fs-4 p-3 mb-3 ${badgeClass}`;
        
        // Update confidence badge
        const confBadge = document.getElementById('confidenceBadge');
        confBadge.textContent = data.confidence;
        confBadge.className = `badge ${this.getConfidenceClass(data.confidence)}`;
        
        // Update explanation
        document.getElementById('overallExplanation').textContent = 
            data.overall_explanation;
        
        // Update technical analysis details
        this.displayTechnicalAnalysis(data.analysis_details);
        
        // Update share functionality
        this.updateShareButtons(data);
        
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
        
        const html = details.map(item => {
            // Handle different data structures from the API
            const indicator = item.method || item.indicator || 'Technical Indicator';
            const analysis = item.explanation || item.analysis || 'Analysis not available';
            const signal = item.signal || 'Unknown';
            const strength = item.strength || 'Unknown';
            
            // Get signal badge styling
            const signalBadge = this.getSignalBadge(signal);
            const strengthBadge = this.getStrengthBadge(strength);
            
            return `
                <div class="border-start border-3 border-primary ps-3 mb-3 technical-analysis-item">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h6 class="mb-0 me-2" style="flex: 1; min-width: 0;">${indicator}</h6>
                        <div class="d-flex gap-1 flex-wrap technical-analysis-badges">
                            ${signalBadge}
                            ${strengthBadge}
                        </div>
                    </div>
                    <p class="mb-0 text-muted">${analysis}</p>
                </div>
            `;
        }).join('');
        
        container.innerHTML = html;
    }
    
    getSignalBadge(signal) {
        const signalLower = signal.toLowerCase();
        if (signalLower.includes('buy') && !signalLower.includes('no')) {
            return '<span class="badge bg-success">Buy</span>';
        } else if (signalLower.includes('no buy') || signalLower === 'no buy') {
            return '<span class="badge bg-danger">No Buy</span>';
        } else {
            return '<span class="badge bg-secondary">Neutral</span>';
        }
    }
    
    getStrengthBadge(strength) {
        const strengthLower = strength.toLowerCase();
        if (strengthLower.includes('strong')) {
            return '<span class="badge bg-success">Strong</span>';
        } else if (strengthLower.includes('moderate')) {
            return '<span class="badge bg-warning">Moderate</span>';
        } else if (strengthLower.includes('weak')) {
            return '<span class="badge bg-secondary">Weak</span>';
        } else {
            return '<span class="badge bg-light text-dark">Unknown</span>';
        }
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
    
    updateShareButtons(data) {
        // Store current analysis data for sharing
        this.currentAnalysis = {
            ticker: data.ticker,
            recommendation: data.recommendation,
            maximum_brain: data.maximum_brain || false
        };
        
        // Update share button onclick handlers
        const twitterBtn = document.getElementById('shareTwitterBtn');
        const facebookBtn = document.getElementById('shareFacebookBtn');
        const linkBtn = document.getElementById('shareLinkBtn');
        
        if (twitterBtn) {
            twitterBtn.onclick = () => this.shareToTwitter();
        }
        if (facebookBtn) {
            facebookBtn.onclick = () => this.shareToFacebook();
        }
        if (linkBtn) {
            linkBtn.onclick = () => this.copyShareLink();
        }
    }
    
    shareToTwitter() {
        if (!this.currentAnalysis) return;
        
        const { ticker, recommendation, maximum_brain } = this.currentAnalysis;
        const shareUrl = maximum_brain 
            ? `${window.location.origin}/share/${ticker}?brain=true`
            : `${window.location.origin}/share/${ticker}`;
        const text = `Just got AI analysis for $${ticker} on @SaneApe_com! 🧠📈 Recommendation: ${recommendation}`;
        const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(shareUrl)}`;
        
        window.open(twitterUrl, '_blank', 'width=550,height=420');
    }
    
    shareToFacebook() {
        if (!this.currentAnalysis) return;
        
        const { ticker, maximum_brain } = this.currentAnalysis;
        const shareUrl = maximum_brain 
            ? `${window.location.origin}/share/${ticker}?brain=true`
            : `${window.location.origin}/share/${ticker}`;
        const facebookUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`;
        
        window.open(facebookUrl, '_blank', 'width=550,height=420');
    }
    
    copyShareLink() {
        if (!this.currentAnalysis) return;
        
        const { ticker, maximum_brain } = this.currentAnalysis;
        const shareUrl = maximum_brain 
            ? `${window.location.origin}/share/${ticker}?brain=true`
            : `${window.location.origin}/share/${ticker}`;
        
        navigator.clipboard.writeText(shareUrl).then(() => {
            const btn = document.getElementById('shareLinkBtn');
            if (btn) {
                const originalHtml = btn.innerHTML;
                btn.innerHTML = '<i data-feather="check" class="me-1"></i>Copied!';
                feather.replace();
                setTimeout(() => {
                    btn.innerHTML = originalHtml;
                    feather.replace();
                }, 2000);
            }
        }).catch(() => {
            // Fallback for older browsers
            const shareUrl = this.currentAnalysis.maximum_brain 
                ? `${window.location.origin}/share/${this.currentAnalysis.ticker}?brain=true`
                : `${window.location.origin}/share/${this.currentAnalysis.ticker}`;
            const textArea = document.createElement('textarea');
            textArea.value = shareUrl;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            
            const btn = document.getElementById('shareLinkBtn');
            if (btn) {
                const originalHtml = btn.innerHTML;
                btn.innerHTML = '<i data-feather="check" class="me-1"></i>Copied!';
                feather.replace();
                setTimeout(() => {
                    btn.innerHTML = originalHtml;
                    feather.replace();
                }, 2000);
            }
        });
    }
    
    async loadRecentAnalyses() {
        try {
            const response = await fetch('/api/recent-analyses');
            const data = await response.json();
            
            if (data.success && data.recent_analyses) {
                this.displayRecentAnalyses(data.recent_analyses);
            } else {
                this.displayRecentAnalyses([]);
            }
        } catch (error) {
            console.error('Error loading recent analyses:', error);
            this.displayRecentAnalyses([]);
        }
    }
    
    displayRecentAnalyses(analyses) {
        const container = document.getElementById('recentAnalysesList');
        
        if (!analyses || analyses.length === 0) {
            container.innerHTML = '<span class="text-muted small">No recent analyses available</span>';
            return;
        }
        
        const html = analyses.map(analysis => {
            const badgeClass = this.getRecommendationBadgeClass(analysis.recommendation);
            const brainIcon = analysis.maximum_brain ? 
                '<i data-feather="cpu" class="me-1" style="width: 12px; height: 12px;"></i>' : '';
            
            return `
                <button class="btn btn-outline-info btn-sm me-2 mb-2 recent-analysis-btn" 
                        data-ticker="${analysis.ticker}" 
                        data-max-brain="${analysis.maximum_brain}"
                        title="${analysis.company_name} - ${analysis.recommendation} (${analysis.confidence}) - Analyzed at ${analysis.analyzed_at}">
                    ${brainIcon}${analysis.ticker}
                    <span class="badge ${badgeClass} ms-1">${this.getShortRecommendation(analysis.recommendation)}</span>
                </button>
            `;
        }).join('');
        
        container.innerHTML = html;
        
        // Add click handlers for recent analysis buttons
        container.querySelectorAll('.recent-analysis-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const ticker = btn.dataset.ticker;
                const maxBrain = btn.dataset.maxBrain === 'true';
                this.loadCachedAnalysis(ticker, maxBrain);
            });
        });
        
        // Re-initialize feather icons
        feather.replace();
    }
    
    getRecommendationBadgeClass(recommendation) {
        const rec = recommendation.toLowerCase();
        if (rec.includes("don't buy") || rec.includes("no,") || rec.includes("no buy")) {
            return 'bg-danger';
        } else if (rec.includes("yes,") || (rec.includes('buy') && !rec.includes("don't"))) {
            return 'bg-success';
        } else {
            return 'bg-secondary';
        }
    }
    
    getShortRecommendation(recommendation) {
        const rec = recommendation.toLowerCase();
        if (rec.includes("don't buy") || rec.includes("no,") || rec.includes("no buy")) {
            return 'No';
        } else if (rec.includes("yes,") || (rec.includes('buy') && !rec.includes("don't"))) {
            return 'Buy';
        } else {
            return '?';
        }
    }
    
    async loadCachedAnalysis(ticker, maxBrain) {
        try {
            this.setAnalyzingState(true);
            
            const response = await fetch(`/api/cached-analysis/${ticker}?maximum_brain=${maxBrain}`);
            const data = await response.json();
            
            if (data.success) {
                this.displayResults(data);
                this.showAlert('success', `Loaded cached analysis for ${ticker} (no rate limit used)`);
            } else {
                this.showAlert('warning', data.error || 'Cached analysis not available');
            }
        } catch (error) {
            console.error('Error loading cached analysis:', error);
            this.showAlert('danger', 'Failed to load cached analysis');
        } finally {
            this.setAnalyzingState(false);
        }
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