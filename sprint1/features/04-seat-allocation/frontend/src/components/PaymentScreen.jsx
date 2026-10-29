/**
 * PaymentScreen.jsx — Phase 5 mock payment
 * ==========================================
 * Simulates the payment flow.
 * 
 * In production: this redirects to a real payment gateway (Razorpay etc.)
 * Here: simulates a 2-second "processing" then calls onPaymentSuccess.
 *
 * Important: The confirm call happens AFTER payment success — never before.
 * (NFR: booking only confirmed after verified successful payment signal)
 */

import { useState } from 'react';

const PAYMENT_METHODS = [
  { id: 'upi',  icon: '📱', name: 'UPI', desc: 'Google Pay, PhonePe, Paytm' },
  { id: 'card', icon: '💳', name: 'Credit / Debit Card', desc: 'Visa, Mastercard, RuPay' },
  { id: 'nb',   icon: '🏦', name: 'Net Banking', desc: 'All major banks supported' },
];

export function PaymentScreen({ selectedSeats, lockInfo, totalAmount, onPaymentSuccess, onBack }) {
  const [selectedMethod, setSelectedMethod] = useState('upi');
  const [processing, setProcessing] = useState(false);

  const handlePay = async () => {
    setProcessing(true);
    // Simulate payment gateway delay (1.5s)
    await new Promise(r => setTimeout(r, 1500));
    setProcessing(false);
    onPaymentSuccess();
  };

  return (
    <div className="payment-screen">
      <button
        className="btn btn-secondary btn-sm"
        onClick={onBack}
        style={{ width: 'auto', marginBottom: 24 }}
      >
        ← Back to Seat Map
      </button>

      <h1 className="page-title">Complete Payment</h1>

      {/* Order summary */}
      <div className="sidebar-card" style={{ marginBottom: 20 }}>
        <div className="sidebar-title">Order Summary</div>
        {selectedSeats.map(s => (
          <div className="price-row" key={s.id}>
            <span>{s.id} ({s.section})</span>
            <span>₹{s.price.toLocaleString('en-IN')}</span>
          </div>
        ))}
        <div className="price-divider" />
        <div className="price-total">
          <span>Total Payable</span>
          <span>₹{totalAmount.toLocaleString('en-IN')}</span>
        </div>
      </div>

      {/* Payment methods */}
      <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
        Choose Payment Method
      </h2>
      <div className="payment-methods">
        {PAYMENT_METHODS.map(method => (
          <div
            key={method.id}
            id={`payment-method-${method.id}`}
            className={`payment-method ${selectedMethod === method.id ? 'selected' : ''}`}
            onClick={() => setSelectedMethod(method.id)}
            role="radio"
            aria-checked={selectedMethod === method.id}
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && setSelectedMethod(method.id)}
          >
            <span className="payment-method-icon">{method.icon}</span>
            <div>
              <div className="payment-method-name">{method.name}</div>
              <div className="payment-method-desc">{method.desc}</div>
            </div>
            {selectedMethod === method.id && (
              <span style={{ marginLeft: 'auto', color: 'var(--brand-400)' }}>✓</span>
            )}
          </div>
        ))}
      </div>

      <button
        id="btn-pay-now"
        className="btn btn-primary"
        disabled={processing}
        onClick={handlePay}
        style={{ marginTop: 8 }}
      >
        {processing ? (
          <>
            <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
            Processing...
          </>
        ) : (
          <>💸 Pay ₹{totalAmount.toLocaleString('en-IN')}</>
        )}
      </button>

      <p className="text-xs text-muted" style={{ textAlign: 'center', marginTop: 12 }}>
        🔒 This is a demo — no real charges will be made.
        <br />In production, this redirects to Razorpay.
      </p>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
