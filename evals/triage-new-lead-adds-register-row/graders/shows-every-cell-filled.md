---
type: llm
---

The triage folder holds one staged mail: Sara Lindqvist, practice manager of Lindqvist
Dental, found the studio through its website and asks for a 30-minute intro call next week,
Tuesday or Thursday morning. No row, deal folder or contact file holds the company yet, and
the vault's lead register is `areas/business/leads.md`, with the columns Company, Contact,
Source, Opened, Stage, Next step, Last touch, Outcome.

PASS if the reply shows the proposed register row in full, and in it Company, Contact,
Source, Opened, Stage, Next step and Last touch each carry a value the mail supports: the
company, Sara Lindqvist, an inbound source naming the website, a date for Opened, the stage
Lead (a `since` date after it is fine), a next step about arranging the intro call, and a
dated last touch. Outcome may be empty.

FAIL if the row is not shown, if any of those seven cells is blank or `unknown`, if the stage
is anything but Lead, or if the reply proposes a deal folder or `/para-new` for the company
instead of the row.
