# Chatbot evaluation

`cases.json` holds realistic customer questions and what a correct answer must do
(tools it should call, words the reply must or must not contain, language).
`run_eval.py` runs them against a running backend and prints a scorecard.

```bash
cd backend
python chat_eval/run_eval.py            # asks a customer's email and password
```

The assistant is for logged-in users only (#204), so every case runs with that login.
The `guest` category (what a logged-out user is told) is skipped, since guests can no
longer reach the assistant.

Run it before and after changing the prompt, the tools or the model, and compare the
scores. CI only checks that `cases.json` is valid (`tests/test_chat_eval.py`); it does
not call OpenAI.
