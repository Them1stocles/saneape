// Mobile-first stock analysis app
class StockAnalyzer {
    constructor() {
        this.form = document.getElementById('stockForm');
        this.tickerInput = document.getElementById('ticker');
        this.analyzeBtn = document.getElementById('analyzeBtn');
        this.btnText = document.getElementById('btnText');
        this.btnLoader = document.getElementById('btnLoader');
        this.alertContainer = document.getElementById('alertContainer');
        this.resultsSection = document.getElementById('resultsSection');
        
        this.initEventListeners();
    }
    
    initEventListeners() {
        // Form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.analyzeStock();
        });
        
        // Real-time ticker validation
        this.tickerInput.addEventListener('input', (e) => {
            this.validateTicker(e.target.value);
        });
        
        // Convert to uppercase
        this.tickerInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.toUpperCase();
        });
    }
    
    validateTicker(ticker) {
        const isValid = /^[A-Z]{1,5}$/.test(ticker);
        
        if (ticker && !isValid) {
            this.tickerInput.classList.add('is-invalid');
        } else {
            this.tickerInput.classList.remove('is-invalid');
        }
        
        return isValid;
    }
    
    showAlert(message, type = 'danger') {
        const alertHTML = `
            <div class="alert alert-${type} alert-dismissible fade show fade-in" role="alert">
                <i data-feather="${type === 'danger' ? 'alert-circle' : 'info'}"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        this.alertContainer.innerHTML = alertHTML;
        feather.replace();
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const alert = this.alertContainer.querySelector('.alert');
            if (alert) {
                alert.remove();
            }
        }, 5000);
    }
    
    setLoading(isLoading) {
        if (isLoading) {
            this.analyzeBtn.disabled = true;
            this.btnText.classList.add('d-none');
            this.btnLoader.classList.remove('d-none');
            this.tickerInput.disabled = true;
        } else {
            this.analyzeBtn.disabled = false;
            this.btnText.classList.remove('d-none');
            this.btnLoader.classList.add('d-none');
            this.tickerInput.disabled = false;
        }
    }
    
    async analyzeStock() {
        const ticker = this.tickerInput.value.trim();
        const maximumBrain = document.getElementById('maximumBrain').checked;
        
        // Validate ticker
        if (!ticker) {
            this.showAlert('Please enter a stock ticker symbol.');
            return;
        }
        
        if (!this.validateTicker(ticker)) {
            this.showAlert('Please enter a valid stock ticker symbol (1-5 letters only).');
            return;
        }
        
        // Clear previous results and alerts
        this.alertContainer.innerHTML = '';
        this.resultsSection.classList.add('d-none');
        
        // Set loading state
        this.setLoading(true);
        
        try {
            const formData = new FormData();
            formData.append('ticker', ticker);
            formData.append('maximum_brain', maximumBrain);
            
            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.displayResults(data);
            } else {
                this.handleError(data, response.status);
            }
            
        } catch (error) {
            console.error('Error:', error);
            this.showAlert('Network error. Please check your connection and try again.');
        } finally {
            this.setLoading(false);
        }
    }
    
    handleError(data, status) {
        let message = data.error || 'An unexpected error occurred.';
        
        if (status === 429) {
            message = 'Rate limit exceeded. You can only make 2 requests per day. Please try again tomorrow.';
        } else if (data.type === 'validation') {
            // Validation errors are already user-friendly
        } else if (data.type === 'analysis') {
            message = `Analysis error: ${data.error}`;
        }
        
        this.showAlert(message);
    }
    
    displayResults(data) {
        // Update stock info
        document.getElementById('stockTitle').textContent = 
            `${data.ticker} - ${data.company_name}`;
        document.getElementById('stockPrice').textContent = 
            `Current Price: $${data.current_price.toFixed(2)}`;
        
        // Update recommendation
        const recommendationBadge = document.getElementById('recommendationBadge');
        recommendationBadge.textContent = data.recommendation;
        
        if (data.recommendation.toLowerCase().includes('buy!')) {
            recommendationBadge.className = 'badge fs-4 p-3 mb-3 recommendation-buy';
        } else {
            recommendationBadge.className = 'badge fs-4 p-3 mb-3 recommendation-no-buy';
        }
        
        // Update confidence
        const confidenceBadge = document.getElementById('confidenceBadge');
        confidenceBadge.textContent = data.confidence.toUpperCase();
        confidenceBadge.className = `badge confidence-${data.confidence.toLowerCase()}`;
        
        // Update explanation
        document.getElementById('overallExplanation').textContent = data.overall_explanation;
        
        // Update technical analysis details
        this.displayTechnicalAnalysis(data.analysis_details);
        
        // Show results with animation
        this.resultsSection.classList.remove('d-none');
        this.resultsSection.classList.add('fade-in');
        
        // Scroll to results on mobile
        if (window.innerWidth <= 768) {
            this.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        
        // Update feather icons
        feather.replace();
    }
    
    displayTechnicalAnalysis(analysisDetails) {
        const container = document.getElementById('technicalAnalysisList');
        
        if (!analysisDetails || analysisDetails.length === 0) {
            container.innerHTML = '<p class="text-muted">No detailed analysis available.</p>';
            return;
        }
        
        const analysisHTML = analysisDetails.map(analysis => {
            const signalClass = analysis.signal.toLowerCase().includes('buy') ? 'buy-signal' : 'no-buy-signal';
            const signalBadgeClass = analysis.signal.toLowerCase().includes('buy') ? 'signal-buy' : 'signal-no-buy';
            const strengthBadgeClass = `strength-${analysis.strength.toLowerCase()}`;
            
            return `
                <div class="technical-analysis-item ${signalClass}">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h6 class="mb-0 fw-bold">${analysis.method}</h6>
                        <div>
                            <span class="badge ${signalBadgeClass} me-2">${analysis.signal}</span>
                            <span class="badge ${strengthBadgeClass}">${analysis.strength}</span>
                        </div>
                    </div>
                    <p class="mb-0 small text-muted">${analysis.explanation}</p>
                </div>
            `;
        }).join('');
        
        container.innerHTML = analysisHTML;
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new StockAnalyzer();
});

// Add some mobile-specific enhancements
if ('serviceWorker' in navigator) {
    // Register service worker for offline functionality (future enhancement)
    // navigator.serviceWorker.register('/sw.js');
}

// Handle orientation changes on mobile
window.addEventListener('orientationchange', () => {
    // Small delay to allow for orientation change to complete
    setTimeout(() => {
        feather.replace();
    }, 100);
});

// Add touch feedback for better mobile experience
document.addEventListener('touchstart', () => {}, { passive: true });
