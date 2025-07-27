# 📋 COMPREHENSIVE IMPLEMENTATION PLAN: User Accounts & Payment Tiers

## **Current System Analysis**

**Current Costs (from CostManager):**
- **Standard Analysis**: ~$0.007 per request (1500 input + 300 output tokens)
- **Maximum Brain**: ~$0.018 per request (4000 input + 800 output tokens)
- **Current Rate Limits**: 6 standard + 2 brain requests per day (IP-based)

**Pricing Strategy:**
- **Standard Analysis**: $0.05 per credit (7x markup)
- **Maximum Brain**: $0.05 per credit × 2 = $0.10 (5.5x markup) 
- **Credit System**: 1 credit = standard, 2 credits = brain

---

## **💰 Subscription Tiers & Credit Allocation**

| Tier | Price | Credits | Cost Per Analysis | Value Proposition |
|------|-------|---------|-------------------|-------------------|
| **Monthly** | $5/month | **100 credits** | $0.05 | ~3 analyses/day |
| **Weekly** | $5/week | **100 credits** | $0.05 | Heavy usage (14/day) |
| **Top-up** | $5/pack | **100 credits** | $0.05 | Pay-as-you-go |
| **Free Tier** | $0 | **6 standard + 2 brain** | N/A | IP-based (current system) |

### **Credit System Rules:**

#### **Subscription Credits** (Monthly/Weekly Plans):
- **NO ROLLOVER**: Unused credits expire at end of billing cycle
- **Automatic Grant**: New credits added on successful payment
- **Payment Failure**: All subscription credits immediately suspended until payment resolved

#### **Top-up Credits** (Credit Packs):
- **UNLIMITED ROLLOVER**: Never expire, accumulate indefinitely  
- **Subscriber Only**: Can only be purchased by users with active subscriptions
- **Payment Independent**: Remain available even if subscription payment fails
- **Priority Usage**: Top-up credits used BEFORE subscription credits

---

## **🏗️ Implementation Architecture**

### **Phase 1: User Authentication (Replit Login)**
```
├── Add Replit Auth Blueprint
├── New Models: User, OAuth
├── Session Management
└── Backwards Compatibility (IP fallback)
```

### **Phase 2: Subscription System (Stripe)**
```
├── New Models: Subscription, CreditBalance, Transaction
├── Stripe Webhook Handlers
├── Credit Management System
└── Subscription Lifecycle
```

### **Phase 3: Credit-Based Rate Limiting**
```
├── Enhanced RateLimiter (User + IP hybrid)
├── Credit Deduction Logic
├── UI Updates (Credit Display)
└── Admin Dashboard Updates
```

---

## **📊 Database Schema Changes**

### **New Models to Add:**

```python
class User(UserMixin, db.Model):
    """Replit-authenticated users"""
    id = db.Column(db.String, primary_key=True)  # Replit user ID
    email = db.Column(db.String, unique=True, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    profile_image_url = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class Subscription(db.Model):
    """User subscription tracking"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('user.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String, unique=True, nullable=True)
    plan_type = db.Column(db.String, nullable=False)  # 'monthly', 'weekly', 'topup'
    status = db.Column(db.String, nullable=False)  # 'active', 'canceled', 'past_due'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class CreditBalance(db.Model):
    """User credit tracking with dual credit system"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('user.id'), nullable=False, unique=True)
    subscription_credits = db.Column(db.Integer, default=0, nullable=False)  # Reset monthly, no rollover
    topup_credits = db.Column(db.Integer, default=0, nullable=False)  # Never expire, rollover enabled
    credits_used_today = db.Column(db.Integer, default=0, nullable=False)
    last_reset_date = db.Column(db.Date, default=datetime.utcnow().date)
    subscription_credits_expiry = db.Column(db.Date, nullable=True)  # End of current billing cycle
    
class CreditTransaction(db.Model):
    """Credit usage history"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('user.id'), nullable=False)
    transaction_type = db.Column(db.String, nullable=False)  # 'subscription_grant', 'topup_purchase', 'usage', 'expiry', 'refund'
    credit_type = db.Column(db.String, nullable=False)  # 'subscription', 'topup'
    credits_amount = db.Column(db.Integer, nullable=False)
    analysis_type = db.Column(db.String, nullable=True)  # 'standard', 'brain'
    ticker_symbol = db.Column(db.String, nullable=True)
    stripe_payment_id = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PaymentFailure(db.Model):
    """Payment failure tracking and retry management"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('user.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String, nullable=False)
    stripe_invoice_id = db.Column(db.String, nullable=False)
    failure_reason = db.Column(db.String, nullable=False)  # 'insufficient_funds', 'expired_card', 'fraud', etc.
    failure_type = db.Column(db.String, nullable=False)  # 'soft_decline', 'hard_decline'
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    next_retry_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String, nullable=False)  # 'pending_retry', 'resolved', 'abandoned'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
```

---

## **⚠️ Potential Issues & Solutions**

### **1. Breaking Changes Risk**
**Problem**: Current users rely on IP-based system
**Solution**: 
- Implement **hybrid rate limiting**: authenticated users use credits, anonymous users use IP limits
- Gradual migration with clear messaging
- Maintain backwards compatibility

### **2. Session Management Complexity**
**Problem**: No current session infrastructure
**Solution**:
- Use existing Flask session configuration 
- Leverage Replit Auth blueprint (already configured)
- 8-hour session timeout (already configured)

### **3. Credit Synchronization**
**Problem**: Race conditions in credit deduction
**Solution**:
- Database transactions with row locking
- Atomic credit operations
- Comprehensive error handling

### **4. Stripe Webhook Security**
**Problem**: Webhook verification and processing
**Solution**:
- Implement Stripe signature verification
- Idempotent webhook processing
- Comprehensive logging

### **5. Frontend Complexity**
**Problem**: Adding auth UI without breaking existing flow
**Solution**:
- Progressive enhancement approach
- Optional login (anonymous users still work)
- Clear upgrade prompts

### **6. Payment Failure Management**
**Problem**: Failed credit card charges and subscription interruptions
**Solution**:
- **Smart Retry Policy**: 3 attempts over 10 days (1 day, 3 days, 7 days)
- **Dunning Management**: Automated email sequences with payment update links
- **Grace Period**: 7-day access suspension before full cancellation
- **Credit Suspension**: Subscription credits suspended during payment failures

### **7. Credit Expiration Complexity**
**Problem**: Dual credit system with different expiration rules
**Solution**:
- **Subscription Credits**: Auto-expire at billing cycle end
- **Top-up Credits**: Never expire, unlimited rollover
- **Usage Priority**: Always use top-up credits first
- **Clear UI Indicators**: Show credit types and expiration status

---

## **🔄 Migration Strategy**

### **Phase 1: Non-Breaking Foundation (Week 1)**
1. Add new database models (additive only)
2. Implement Replit Auth (optional login)
3. Create user registration flow
4. Maintain full IP-based functionality

### **Phase 2: Credit System (Week 2)**
1. Add Stripe integration
2. Implement credit purchasing
3. Create subscription management
4. Add credit display to UI

### **Phase 3: Enhanced Rate Limiting (Week 3)**
1. Update RateLimiter to support both systems
2. Add credit deduction logic
3. Update frontend credit display
4. Admin dashboard enhancements

### **Phase 4: Optimization & Polish (Week 4)**
1. Performance optimization
2. Error handling improvements  
3. User experience refinements
4. Analytics and monitoring

---

## **🎯 Frontend Changes Required**

### **New UI Components:**
- **Login/Logout buttons** (top navigation)
- **Dual credit balance display** (subscription vs top-up credits)
- **Subscription management page** with payment failure status
- **Purchase top-up credits modal** (subscribers only)
- **Payment method update interface**
- **Upgrade prompts** for free users
- **User profile menu**

### **Enhanced Existing:**
- **Analysis form**: Show credit cost and available balance breakdown
- **Results page**: Update credit balance with priority usage indication
- **Rate limit messaging**: Credits vs IP-based limits
- **Payment failure alerts**: Clear notification of suspended access

### **Credit Display Logic:**
```javascript
// Example credit display
{
  topup_credits: 47,        // Never expire
  subscription_credits: 23, // Expire 2025-08-27
  total_available: 70,
  usage_priority: "Top-up credits used first"
}
```

---

## **💳 Stripe Integration Details**

### **Products to Create:**
```javascript
// Monthly Subscription
{
  name: "SaneApe Monthly",
  price: $5.00,
  recurring: { interval: "month" },
  credits: 100
}

// Weekly Subscription  
{
  name: "SaneApe Weekly", 
  price: $5.00,
  recurring: { interval: "week" },
  credits: 100
}

// Credit Top-up
{
  name: "Credit Pack",
  price: $5.00,
  one_time: true,
  credits: 100
}
```

### **Webhook Events to Handle:**
- `customer.subscription.created` → Grant initial subscription credits
- `customer.subscription.updated` → Handle plan changes
- `customer.subscription.deleted` → Expire subscription credits immediately
- `invoice.payment_succeeded` → Grant monthly credits, resolve payment failures
- `invoice.payment_failed` → Suspend subscription credits, initiate retry sequence
- `invoice.payment_action_required` → Notify user of authentication needs
- `customer.subscription.past_due` → Suspend access, send dunning emails

---

## **💳 Payment Failure & Recovery Strategy**

### **Smart Retry Policy (Industry Best Practice)**
```
Failure Type Classification:
├── Soft Declines (network issues, temporary fraud alerts)
│   └── Retry immediately, then 1 day, 3 days
├── Hard Declines (insufficient funds, expired card)
│   └── Retry 1 day, 3 days, 7 days (near paydays)
└── Authentication Required (3D Secure)
    └── Immediate notification, 72-hour window
```

### **Dunning Management Sequence**
1. **Day 0**: Payment fails → Immediate email with payment update link
2. **Day 1**: First retry attempt + reminder email
3. **Day 3**: Second retry + "Update Payment Method" email
4. **Day 7**: Final retry + "Subscription at Risk" warning
5. **Day 14**: Subscription cancelled, grace period begins
6. **Day 21**: Account deactivated, final recovery email

### **Credit Suspension Logic**
```python
# Payment failure handling
def handle_payment_failure(user_id, failure_type):
    if failure_type in ['insufficient_funds', 'expired_card']:
        suspend_subscription_credits(user_id)  # Keep top-up credits
        schedule_retry_sequence(user_id)
        send_payment_failure_notification(user_id)
    
    # Top-up credits remain unaffected
```

### **Recovery Metrics (Industry Standards)**
- **Target Recovery Rate**: 15-25% of failed payments
- **Average Recovery Time**: 5-7 days
- **Grace Period**: 7 days before service suspension

---

## **🔄 Dual Credit System Implementation**

### **Credit Usage Priority (Always This Order):**
1. **Top-up Credits** (never expire, purchased by subscribers)
2. **Subscription Credits** (expire monthly, granted with subscription)

### **Monthly Credit Reset Logic**
```python
def handle_billing_cycle_renewal(user_id):
    # Expire all unused subscription credits (NO ROLLOVER)
    expire_subscription_credits(user_id)
    
    # Grant new subscription credits for new billing period
    grant_subscription_credits(user_id, plan_credits=100)
    
    # Top-up credits remain untouched (unlimited rollover)
```

### **Top-up Purchase Restrictions**
- **Subscriber Only**: Must have active subscription to purchase
- **Payment Failed**: Can still use existing top-ups during suspension
- **Post-Cancellation**: No new top-up purchases allowed

---

## **📈 Expected Performance Impact**

### **Database Queries:**
- **Current**: 1-2 queries per analysis (IP lookup + cache)
- **With Users**: 2-3 queries per analysis (user + credits + cache)
- **Estimated Impact**: <100ms additional latency

### **Memory Usage:**
- **Additional Models**: ~50MB for 10k users
- **Session Storage**: ~10MB for 1k concurrent users
- **Total Impact**: Minimal for expected user base

---

## **🛡️ Security Considerations**

### **Authentication Security:**
- Leverage Replit's OAuth security
- CSRF protection on all forms
- Secure session management

### **Payment Security:**
- Stripe handles all card data (PCI compliant)
- Webhook signature verification
- Idempotent payment processing

### **Rate Limiting Security:**
- Prevent credit farming attacks
- Monitor suspicious purchase patterns
- IP-based backup protection

---

## **📊 Success Metrics**

### **Technical Metrics:**
- Zero downtime during migration
- <100ms latency increase
- 99.9% payment success rate

### **Business Metrics:**
- User conversion rate: >5%
- Average revenue per user: $5-20/month
- Churn rate: <10%/month

---

## **🚀 Go/No-Go Decision Points**

### **Prerequisites:**
✅ PostgreSQL database ready  
✅ Stripe account setup required  
✅ Replit Auth configuration needed  
✅ STRIPE_SECRET_KEY environment variable required  

### **Risk Assessment:** **LOW-MEDIUM**
- Well-established patterns (Replit Auth + Stripe)
- Backwards compatibility maintained  
- Incremental rollout possible
- Rollback plan available

---

## **📝 Final Implementation Order**

1. **Environment Setup**: Stripe keys, Replit auth configuration
2. **Database Models**: Add new tables (non-breaking)
3. **Replit Authentication**: User login/logout system  
4. **Credit System**: Balance tracking and display
5. **Stripe Integration**: Payment processing and webhooks
6. **Enhanced Rate Limiting**: Hybrid user/IP system
7. **Frontend Polish**: Credit display and subscription management
8. **Testing & Optimization**: Performance and error handling

**Estimated Timeline:** 3-4 weeks for full implementation  
**Risk Level:** Low (backwards compatible, incremental)  
**Revenue Impact:** Potential $500-2000/month with 100-400 paying users

---

**Status:** ✅ **COMPREHENSIVE PLAN COMPLETE** ✅  
**Next Steps:** Ready for implementation approval

---

## **📋 Summary of Key Requirements Addressed:**

### **✅ Payment Failure Handling:**
- Smart retry policy with 3 attempts over 10 days
- Dunning management email sequences
- Grace period before cancellation
- Credit suspension during payment failures

### **✅ Credit Expiration Rules:**
- **Subscription Credits**: ZERO rollover, expire monthly
- **Top-up Credits**: UNLIMITED rollover, never expire
- **Usage Priority**: Top-up credits always used first

### **✅ Business Model Protection:**
- Top-up purchases restricted to active subscribers only
- Payment-independent top-up credit availability
- Clear separation of credit types with different rules
- Comprehensive payment failure recovery system

This plan ensures sustainable revenue while providing excellent user experience through the dual credit system.