# Chatbot evaluation

`cases.json` holds realistic customer questions and what a correct answer must do
(tools it should call, words the reply must or must not contain, language).
`run_eval.py` runs them against a running backend and prints a scorecard.

```bash
cd backend
python chat_eval/run_eval.py            # guest cases
python chat_eval/run_eval.py --login    # all cases (asks a customer's email and password)
```

Run it before and after changing the prompt, the tools or the model, and compare the
scores. CI only checks that `cases.json` is valid (`tests/test_chat_eval.py`); it does
not call OpenAI.
