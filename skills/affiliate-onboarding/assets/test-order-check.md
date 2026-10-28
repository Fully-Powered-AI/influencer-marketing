# Test the code before the creator hears about it

One sheet per creator. The person who runs it fills it in; nothing here is sent to the creator.

- creator_ref:
- code:
- link:
- rail (programme section 6):
- discount programme section 4 sets:
- tested by (role, from programme section 10):
- date (YYYY-MM-DD):

## The checks

1. The code exists on the rail. Manual rail: the plan row is `minted`, or the code was created in the Shopify admin from the plan row. Collabs or app: the code and the link show against this creator in the rail's own dashboard.
   Seen:
2. Open the link in a private browser window. It reaches the store page programme section 5 names; on the manual rail the address still carries its `utm_` values when the page loads.
   Seen:
3. Put a product in the cart, go to checkout and enter the code. Write the discount exactly as checkout shows it.
   Seen:
4. If the store has another active code (for example a first-order newsletter code) or an automatic discount running, try it with the creator's code. Write whether they combined, and whether that is what the owner decided.
   Seen:
5. Either stop before paying (record `--tested checkout`), or place a low-value order (record `--tested order:<order name>`, the name as the orders export shows it, for example `#1043`). The recording script writes the dated entry `YYYY-MM-DD test order #1043` (the test date; give `--tested-on` if you record on a later day) into the creator's roster notes, and `commission-statement` and `performance-report` leave that order out. Cancel or refund it afterwards if the owner wants the stock and the money back.
   Done:

## Result

- Discount matches programme section 4: yes / no
- Combines with other discounts: yes / no / not tested
- If anything was a no: fix it on the rail, or bring it to the owner, then test again. The creator hears nothing until every line here reads as it should.

Record the result with `scripts/record_onboarding.py`, giving `--discount-seen` exactly as written in check 3.
