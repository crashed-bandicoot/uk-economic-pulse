# uk-economic-pulse
A live system that answers one question: What the hell is going on in the economy?

# Practical guide to the workflow

Use notebooks for
- testing API calls
- checking dataframe shape
- trying feature engineering
- plotting and interpreting results

Example, you test a framework in a notebook. 
Once it works, you move it into fetch.py. 
Import it back into the notebook.
Now your notebook becomes thinner and cleaner.

That’s the rhythm:
discover in notebook, formalize in Python file, reuse from notebook.