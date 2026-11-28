# Sequence Diagram: Review Submission and AI Sentiment Analysis

## 1. Description and Purpose
This sequence diagram models customer and critic review publishing, rating storage, historical version snapshotting upon edits, and automated background AI review summarization using OpenAI.

## 2. Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor Reviewer as Customer / Critic
    participant NextJS as Next.js Frontend
    participant ReviewCtrl as reviews.py (API)
    participant AISvc as ai_review_summary_service.py
    participant DB as PostgreSQL 16
    participant OpenAI as OpenAI Platform (API)

    %% 1. Submit New Review
    Reviewer ->> NextJS: Open /events/{eventId}/reviews, submit 5-star review
    NextJS ->> ReviewCtrl: POST /api/reviews/events/{eventId} {rating: 5, title: "Magnificent show!", content: "...", is_critic: false}
    
    ReviewCtrl ->> DB: Verify user has confirmed booking for this event (or critic credentials)
    ReviewCtrl ->> DB: INSERT INTO reviews (event_id, user_id, rating, title, content, is_critic, status='active')
    DB -->> ReviewCtrl: review_id
    ReviewCtrl -->> NextJS: 201 Created {review_id, rating: 5}
    NextJS -->> Reviewer: Display review in list

    %% 2. Background AI Review Summarization Trigger
    opt Review Count Threshold or On-Demand Request
        ReviewCtrl ->> AISvc: refresh_event_ai_summary(event_id)
        AISvc ->> DB: Fetch all active reviews for event_id
        DB -->> AISvc: List of reviews (ratings, text contents)
        AISvc ->> OpenAI: POST /v1/chat/completions (Prompt: extract sentiment, pros, cons, summary)
        OpenAI -->> AISvc: 200 OK JSON {summary: "...", sentiment_score: 0.92, pros: [...], cons: [...]}
        AISvc ->> DB: UPSERT INTO ai_review_summaries (event_id, summary, sentiment_score, pros, cons, generated_at=NOW())
    end

    %% 3. Customer Edits Review
    Reviewer ->> NextJS: Edits review text -> Click "Save Changes"
    NextJS ->> ReviewCtrl: PATCH /api/reviews/{review_id} {rating: 4, content: "Updated review..."}
    ReviewCtrl ->> DB: Fetch existing review row
    ReviewCtrl ->> DB: INSERT INTO review_versions (review_id, rating, title, content, edited_at=NOW())
    ReviewCtrl ->> DB: UPDATE reviews SET rating=4, content="Updated review...", updated_at=NOW() WHERE id=$review_id AND user_id=$user
    ReviewCtrl -->> NextJS: 200 OK (Review updated with version history logged)
    NextJS -->> Reviewer: Update UI to show "(edited)" indicator
```

## 3. Important Implementation Notes
- **Review Version Auditing:** To prevent deceptive post-hoc edits, every update to an existing review automatically archives a complete snapshot into `review_versions` before modifying the parent row in `reviews`.
- **Verified Purchase / Attendance Check:** Customers can only review events for which they hold a confirmed booking (`reviews.py` enforces booking verification).
