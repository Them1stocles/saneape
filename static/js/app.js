// Enhanced SaneApe.com Application with Dynamic UI and Rate Limiting
class SaneApeApp {
    constructor() {
        this.form = document.getElementById('stockForm');
        this.tickerInput = document.getElementById('ticker');
        this.maxBrainCheck = document.getElementById('maximumBrain');
        this.incomeFocusCheck = document.getElementById('incomeFocus');
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
    
    /**
     * PRODUCTION-GRADE UNICODE TEXT NORMALIZATION UTILITY
     * Handles all apostrophe variants that OpenAI might return
     * Prevents display bugs caused by Unicode character mismatches
     */
    normalizeRecommendationText(text) {
        if (!text || typeof text !== 'string') return '';
        
        return text
            // Smart quotes and apostrophes: ' ' ‚ ‛
            .replace(/[\u2018\u2019\u201A\u201B]/g, "'")
            // Modifier apostrophes and stress marks
            .replace(/[\u02BC\u02C8]/g, "'")
            // Grave and acute accents used as apostrophes  
            .replace(/[\u0060\u00B4]/g, "'")
            // Additional Unicode apostrophe variants
            .replace(/[\u055A\u07F4\u07F5]/g, "'")
            // Normalize whitespace
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
    }
    
    /**
     * PRODUCTION-GRADE RECOMMENDATION PARSER
     * Robust pattern matching for all possible OpenAI recommendation formats
     * Fixes critical Unicode apostrophe bug that caused "No, don't buy!" to display as green "Buy"
     */
    parseRecommendation(rawRecommendation, incomeAnalysis = null, isIncomeMode = false) {
        const normalized = this.normalizeRecommendationText(rawRecommendation);
        
        // Income analysis override takes priority
        if (incomeAnalysis && incomeAnalysis.recommendation && isIncomeMode) {
            const incomeNormalized = this.normalizeRecommendationText(incomeAnalysis.recommendation);
            if (incomeNormalized.includes('buy for income') || 
                (incomeNormalized.includes('buy') && incomeNormalized.includes('income'))) {
                return {
                    displayText: "Buy for Income",
                    badgeClass: 'bg-success',
                    confidence: 'income-focused'
                };
            }
        }
        
        // Comprehensive "No Buy" patterns - FIXES UNICODE APOSTROPHE BUG
        const noBuyPatterns = [
            "don't buy",           // Now handles ALL apostrophe variants
            "do not buy", 
            "no, don't buy",
            "no, do not buy",
            "not recommended",
            "avoid buying",
            "avoid",
            "sell",
            "short"
        ];
        
        const noBuyRegexPatterns = [
            /\bno\b.*\bbuy\b/,           // "no ... buy"
            /\bavoid\b.*\bbuying\b/,     // "avoid ... buying"
            /\bnot\b.*\brecommend/,      // "not ... recommend"
            /\bdon't\b.*\bbuy\b/         // "don't ... buy" (normalized apostrophe)
        ];
        
        // Check explicit no-buy patterns
        for (const pattern of noBuyPatterns) {
            if (normalized.includes(pattern)) {
                return {
                    displayText: "No Buy",
                    badgeClass: 'bg-danger',
                    confidence: 'negative'
                };
            }
        }
        
        // Check regex patterns for no-buy
        for (const regex of noBuyRegexPatterns) {
            if (regex.test(normalized)) {
                return {
                    displayText: "No Buy", 
                    badgeClass: 'bg-danger',
                    confidence: 'negative'
                };
            }
        }
        
        // Comprehensive "Buy" patterns 
        const buyPatterns = [
            "yes, buy",
            "yes buy",
            "recommend buying",
            "strong buy",
            "buy signal",
            "bullish",
            "buy recommendation"
        ];
        
        // Check explicit buy patterns
        for (const pattern of buyPatterns) {
            if (normalized.includes(pattern)) {
                return {
                    displayText: "Buy",
                    badgeClass: 'bg-success', 
                    confidence: 'positive'
                };
            }
        }
        
        // Final check: contains "buy" but not negative indicators
        if (normalized.includes('buy') && 
            !normalized.includes("don't") && 
            !normalized.includes("not") &&
            !normalized.includes("avoid") &&
            !normalized.includes("no,")) {
            return {
                displayText: "Buy",
                badgeClass: 'bg-success',
                confidence: 'positive'
            };
        }
        
        // Fallback for unknown patterns
        console.warn('Unknown recommendation pattern detected:', rawRecommendation);
        console.warn('Normalized text:', normalized);
        return {
            displayText: rawRecommendation || "Unknown",
            badgeClass: 'bg-warning',
            confidence: 'unknown'
        };
    }
    
    setupEventListeners() {
        // Form submission
        this.form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        
        // Real-time input validation
        this.tickerInput.addEventListener('input', () => this.validateInput());
        
        // Maximum Brain checkbox change
        this.maxBrainCheck.addEventListener('change', () => {
            this.updateButtonState();
            
            // Google Analytics toggle event
            if (typeof gtag !== 'undefined') {
                gtag('event', 'maximum_brain_toggle', {
                    'enabled': this.maxBrainCheck.checked,
                    'event_category': 'ui_interaction',
                    'event_label': this.maxBrainCheck.checked ? 'enabled' : 'disabled'
                });
            }
        });
        
        // Income Focus checkbox change
        if (this.incomeFocusCheck) {
            this.incomeFocusCheck.addEventListener('change', () => {
                this.updateButtonState();
                
                // Google Analytics toggle event
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'income_focus_toggle', {
                        'enabled': this.incomeFocusCheck.checked,
                        'event_category': 'ui_interaction',
                        'event_label': this.incomeFocusCheck.checked ? 'enabled' : 'disabled'
                    });
                }
            });
        }
        
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
        const incomeFocus = this.incomeFocusCheck ? this.incomeFocusCheck.checked : false;
        
        this.setAnalyzingState(true);
        this.clearAlerts();
        this.hideResults();
        
        // Google Analytics event tracking
        if (typeof gtag !== 'undefined') {
            gtag('event', 'stock_analysis_start', {
                'ticker_symbol': ticker,
                'analysis_type': maximumBrain ? 'maximum_brain' : 'standard',
                'event_category': 'analysis',
                'event_label': ticker
            });
        }
        
        try {
            const formData = new FormData();
            formData.append('ticker', ticker);
            formData.append('maximum_brain', maximumBrain.toString());
            formData.append('income_focus', incomeFocus.toString());
            
            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.displayResults(data);
                this.showAlert('Analysis completed successfully!', 'success');
                
                // Google Analytics success event
                if (typeof gtag !== 'undefined') {
                    const analysisType = maximumBrain ? 'maximum_brain' : 'standard';
                    const finalType = incomeFocus ? `${analysisType}_income` : analysisType;
                    gtag('event', 'stock_analysis_complete', {
                        'ticker_symbol': ticker,
                        'analysis_type': finalType,
                        'income_focus': incomeFocus,
                        'recommendation': data.recommendation,
                        'confidence': data.confidence,
                        'event_category': 'analysis',
                        'event_label': ticker
                    });
                }
                
                // Refresh user status to update remaining requests
                await this.loadUserStatus();
            } else {
                this.handleError(data.error, data.type);
                
                // Google Analytics error event
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'stock_analysis_error', {
                        'ticker_symbol': ticker,
                        'analysis_type': maximumBrain ? 'maximum_brain' : 'standard',
                        'error_type': data.type || 'unknown',
                        'error_message': data.error,
                        'event_category': 'analysis',
                        'event_label': ticker
                    });
                }
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
        

        
        // Standardize the text for consistency
        let displayText;
        let badgeClass;
        
        // Check for income-focused override
        const hasIncomeOverride = data.income_analysis && 
                                 data.income_analysis.recommendation && 
                                 normalizeApostrophes(data.income_analysis.recommendation).includes('buy for income') &&
                                 (data.income_focus || data.is_yield_etf);
        
        if (hasIncomeOverride) {
            displayText = "Buy for Income";
            badgeClass = 'bg-success';
        } else {
            // PRODUCTION-GRADE RECOMMENDATION PARSING
            const result = this.parseRecommendation(
                data.recommendation, 
                data.income_analysis,
                data.income_focus || data.is_yield_etf
            );
            displayText = result.displayText;
            badgeClass = result.badgeClass;
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
        
        // Update income analysis if available
        this.displayIncomeAnalysis(data.income_analysis, data.income_focus || data.is_yield_etf);
        
        // Update share functionality
        this.updateShareButtons(data);
        
        // Show results
        this.resultsSection.classList.remove('d-none');
        this.resultsSection.scrollIntoView({ behavior: 'smooth' });
        
        // Re-initialize feather icons for new content
        feather.replace();
        
        // Initialize Bootstrap tooltips for new content
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
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
    
    displayIncomeAnalysis(incomeData, showIncomeSection) {
        const incomeContainer = document.getElementById('incomeAnalysisAccordion');
        
        if (!showIncomeSection || !incomeData) {
            if (incomeContainer) {
                incomeContainer.style.display = 'none';
            }
            return;
        }
        
        if (incomeContainer) {
            incomeContainer.style.display = 'block';
            
            // Update income analysis content
            const incomeDetailsContainer = document.getElementById('incomeAnalysisList');
            if (incomeDetailsContainer && incomeData.metrics) {
                const metrics = incomeData.metrics;
                
                const incomeHtml = `
                    <div class="alert alert-info mb-3">
                        <h6 class="alert-heading">Payment Schedule</h6>
                        <p class="mb-1">
                            <strong>Frequency:</strong> ${metrics.payment_frequency || 'Unknown'} 
                            (${metrics.payments_per_year || 'N/A'} payments/year)
                            ${metrics.dividend_count_last_year ? `• ${metrics.dividend_count_last_year} payments in last 12 months` : ''}
                        </p>
                        ${metrics.frequency_note ? `<small class="text-muted"><i data-feather="info" style="width: 12px; height: 12px;"></i> ${metrics.frequency_note}</small>` : ''}
                    </div>
                    
                    <div class="row g-3 mb-4">
                        <div class="col-md-6">
                            <div class="card border-success">
                                <div class="card-body text-center">
                                    <h6 class="card-title">Effective Income Return</h6>
                                    <div class="h4 text-success">${metrics.effective_return ? metrics.effective_return.toFixed(2) : 'N/A'}%</div>
                                    <small class="text-muted">After all costs</small>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card border-info">
                                <div class="card-body text-center">
                                    <h6 class="card-title">Annualized Distribution Yield</h6>
                                    <div class="h4 text-info">${metrics.annualized_yield ? metrics.annualized_yield.toFixed(2) : 'N/A'}%</div>
                                    <small class="text-muted">Based on ${metrics.payment_frequency || 'estimated'} payments</small>
                                </div>
                            </div>
                        </div>
                        ${metrics.nav_decay_rate !== undefined ? `
                        <div class="col-md-6">
                            <div class="card border-warning">
                                <div class="card-body text-center">
                                    <h6 class="card-title">NAV Decay Rate</h6>
                                    <div class="h5 text-warning">${metrics.nav_decay_rate.toFixed(2)}%</div>
                                </div>
                            </div>
                        </div>
                        ` : ''}
                        ${metrics.roc_percentage !== undefined ? `
                        <div class="col-md-6">
                            <div class="card border-primary">
                                <div class="card-body text-center">
                                    <h6 class="card-title">
                                        Return of Capital %
                                        <i data-feather="info" class="ms-1" style="width: 14px; height: 14px;" 
                                           data-bs-toggle="tooltip" data-bs-placement="top" 
                                           title="Percentage of distributions that are return of your original investment (principal) rather than earnings. Return of capital is not immediately taxable but reduces your cost basis."></i>
                                    </h6>
                                    <div class="h5 text-primary">${metrics.roc_percentage.toFixed(2)}%</div>
                                    <small class="text-muted">Of total distributions</small>
                                </div>
                            </div>
                        </div>
                        ` : ''}
                    </div>
                    
                    ${incomeData.recommendation ? `
                    <div class="alert alert-${incomeData.recommendation.includes('Buy') ? 'success' : 'warning'} mb-3">
                        <h6 class="alert-heading">Income Recommendation</h6>
                        <p class="mb-1"><strong>${incomeData.recommendation}</strong></p>
                        <p class="mb-0">${incomeData.explanation || ''}</p>
                    </div>
                    ` : ''}
                    
                    ${incomeData.key_risks && incomeData.key_risks.length > 0 ? `
                    <div class="alert alert-danger">
                        <h6 class="alert-heading">Key Income Risks</h6>
                        <ul class="mb-0">
                            ${incomeData.key_risks.map(risk => `<li>${risk}</li>`).join('')}
                        </ul>
                    </div>
                    ` : ''}
                `;
                
                incomeDetailsContainer.innerHTML = incomeHtml;
            }
        }
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
        // Determine effective recommendation (with income override)
        let effectiveRecommendation = data.recommendation;
        
        const hasIncomeOverride = data.income_analysis && 
                                 data.income_analysis.recommendation && 
                                 data.income_analysis.recommendation.toLowerCase().includes('buy for income') &&
                                 (data.income_focus || data.is_yield_etf);
        
        if (hasIncomeOverride) {
            effectiveRecommendation = "Buy for Income";
        }
        
        // Store current analysis data for sharing
        this.currentAnalysis = {
            ticker: data.ticker,
            recommendation: effectiveRecommendation,
            maximum_brain: data.maximum_brain || false,
            has_income_override: hasIncomeOverride
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
        const text = `Just got AI analysis for $${ticker} on @saneape! 🧠📈 Recommendation: ${recommendation}. Ape on data, not vibes - a sanity check for late night traders & hopium addicts.`;
        const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(shareUrl)}`;
        
        // Google Analytics share event
        if (typeof gtag !== 'undefined') {
            gtag('event', 'share', {
                'method': 'twitter',
                'content_type': 'stock_analysis',
                'item_id': ticker,
                'analysis_type': maximum_brain ? 'maximum_brain' : 'standard',
                'event_category': 'social',
                'event_label': ticker
            });
        }
        
        window.open(twitterUrl, '_blank', 'width=550,height=420');
    }
    
    shareToFacebook() {
        if (!this.currentAnalysis) return;
        
        const { ticker, maximum_brain } = this.currentAnalysis;
        const shareUrl = maximum_brain 
            ? `${window.location.origin}/share/${ticker}?brain=true`
            : `${window.location.origin}/share/${ticker}`;
        const facebookUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`;
        
        // Google Analytics share event
        if (typeof gtag !== 'undefined') {
            gtag('event', 'share', {
                'method': 'facebook',
                'content_type': 'stock_analysis',
                'item_id': ticker,
                'analysis_type': maximum_brain ? 'maximum_brain' : 'standard',
                'event_category': 'social',
                'event_label': ticker
            });
        }
        
        window.open(facebookUrl, '_blank', 'width=550,height=420');
    }
    
    copyShareLink() {
        if (!this.currentAnalysis) return;
        
        const { ticker, maximum_brain } = this.currentAnalysis;
        const shareUrl = maximum_brain 
            ? `${window.location.origin}/share/${ticker}?brain=true`
            : `${window.location.origin}/share/${ticker}`;
        
        // Google Analytics share event
        if (typeof gtag !== 'undefined') {
            gtag('event', 'share', {
                'method': 'copy_link',
                'content_type': 'stock_analysis',
                'item_id': ticker,
                'analysis_type': maximum_brain ? 'maximum_brain' : 'standard',
                'event_category': 'social',
                'event_label': ticker
            });
        }
        
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
                
                // Google Analytics event tracking
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'recent_analysis_click', {
                        'ticker_symbol': ticker,
                        'analysis_type': maxBrain ? 'maximum_brain' : 'standard',
                        'event_category': 'engagement',
                        'event_label': ticker
                    });
                }
                
                this.loadCachedAnalysis(ticker, maxBrain);
            });
        });
        
        // Re-initialize feather icons
        feather.replace();
    }
    
    getRecommendationBadgeClass(recommendation) {
        const rec = recommendation.toLowerCase();
        if (rec.includes("buy for income")) {
            return 'bg-success';
        } else if (rec.includes("don't buy") || rec.includes("no,") || rec.includes("no buy")) {
            return 'bg-danger';
        } else if (rec.includes("yes,") || (rec.includes('buy') && !rec.includes("don't"))) {
            return 'bg-success';
        } else {
            return 'bg-secondary';
        }
    }
    
    getShortRecommendation(recommendation) {
        const rec = recommendation.toLowerCase();
        if (rec.includes("buy for income")) {
            return 'Buy Income';
        } else if (rec.includes("don't buy") || rec.includes("no,") || rec.includes("no buy")) {
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
                
                // Google Analytics cached analysis event
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'cached_analysis_load', {
                        'ticker_symbol': ticker,
                        'analysis_type': maxBrain ? 'maximum_brain' : 'standard',
                        'event_category': 'analysis',
                        'event_label': ticker
                    });
                }
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