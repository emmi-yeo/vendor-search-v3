AI Vendor Search – Feature Upgrade Specification
1. Smart Vendor Search (Core Upgrade)
1.1 AI-Driven Vendor Matching

Description
Enhance vendor search using AI to match vendors based on multiple dimensions, not just keywords.

Matching dimensions

Category / Industry

Location (country, state, city)

Compliance (certifications, tax registration, statutory filings)

Performance (transaction volume, spend, delivery history, evaluation scores)

Example queries

“ISO-certified IT vendors in Malaysia”

“Top 10 vendors by spend in Q4”

“Vendors flagged for missing tax registration”

Expected behavior

Natural language understanding

Vendors ranked by relevance

Explainable reasons for ranking

Priority: High
Intent: Make search usable without knowing exact filters

2. Vendor Search with Attachments (Unstructured Data)
2.1 Attachment-Aware Search in Chat

Description
Allow the AI search to extract and reason over vendor attachments.

Supported attachment types

Images (JPEG, PNG)

PDF documents

Microsoft Office files:

Word

Excel

PowerPoint

Capabilities

Extract relevant text/data from attachments

Use extracted content as part of vendor matching

Answer questions like:

“Which vendors mentioned SOC monitoring in their proposals?”

“Vendors with ISO certificates uploaded”

Priority: High
Intent: Unlock value from documents already stored in eProc

3. Multi-Criteria Search Logic (Advanced Filtering)
3.1 AND / OR Logic Across Criteria

Description
Support complex multi-criteria queries with logical operators.

Examples

Vendors with ISO27001 AND SOC experience

Vendors in Malaysia OR Singapore

Vendors with ISO certification AND (IT OR Cybersecurity)

Expected behavior

AI understands logical intent from natural language

UI optionally visualizes interpreted logic

Priority: High
Intent: Enable enterprise-grade filtering without complex UI

4. Fine-Tunable Search Result Output (AI-Controlled Layout)
4.1 Custom Output Layout & Content

Description
Allow users to instruct the AI to control how results are presented.

Customizable elements

Columns / data fields shown

Field order

Field labels

Date format

Numeric format

Example instructions

“Show vendor name, country, ISO status only”

“Format dates as DD/MM/YYYY”

“Group vendors by industry”

Priority: Medium
Intent: Reduce manual reformatting and copying

4.2 Ranked Output with Scores

Description
Enhance ranking output with explicit scores.

Score types

Relevance score

Compliance score

Risk score

Sorting options

By relevance (default)

By compliance risk

By spend

By performance indicators

Priority: Medium
Intent: Support decision-making, not just discovery

5. Export & Sharing
5.1 Export Search Results

Supported formats

Excel

CSV

PDF

Options

Export full result set

Export current filtered view

Export ranked results with scores

Priority: Medium
Intent: Allow reuse in reporting, approvals, presentations

5.2 Copy-Paste Friendly Output

Description

Clean table formatting for direct copy into:

Emails

Documents

Spreadsheets

Priority: Low
Intent: Reduce friction in daily work

6. Fuzzy Matching & Semantic Understanding
6.1 Fuzzy Matching for Misspellings

Description

Detect and match:

Typos

Abbreviations

Naming variations

Language differences

Examples

“Cyber sec” → Cybersecurity

“ISO 27k” → ISO27001

Company name variations

Priority: Medium
Intent: Improve recall without sacrificing precision

6.2 Semantic Meaning Matching

Description

Understand “close enough” intent

Match conceptually similar terms, not just literal text

Priority: Medium
Intent: Make AI search feel intelligent, not brittle

7. Contextual eProcurement Intelligence
7.1 Vendor-Related Transaction Context

Description
Allow users to explore procurement context related to a vendor.

Supported contexts

Vendor performance evaluations

Sourcing events participated

Awards won / lost

Invoices submitted

Spend history

Delivery issues or flags

Example queries

“Show performance issues for this vendor”

“What sourcing events did this vendor participate in?”

Priority: Medium
Intent: Move from search → insight

8. Predefined & Guided Prompts (Low Priority)
8.1 Predefined Prompt Library

Description
Provide clickable prompts for common queries.

Examples

Show vendor updates

Show vendor financial stability

Show vendor reputation & references

Show vendor shareholders

Priority: Low
Intent: Help less technical users get started

9. Duplicate Vendor Detection (Related Function)
9.1 AI-Based Duplication Detection

Description
Detect potential duplicate vendor records.

Signals

Similar names

Similar addresses

Similar registration numbers

Language / spelling variants

Output

Suggested duplicate pairs

Confidence score

Reason for match

Priority: Medium
Intent: Improve data quality and governance

10. External Vendor Intelligence (Optional / Advanced)
10.1 External Information Enrichment

Description
Augment vendor data with external sources.

Possible sources

Public websites

Business registries

News articles

Use cases

Reputation checks

Financial red flags

Public compliance issues

Priority: Low
Intent: Enrich internal data (requires governance)

11. UX Enhancements & Utilities
11.1 Deep Links to Vendor Records

Direct URL to vendor profile in eProc / VMS

11.2 Pagination & Large Result Handling

Handle large result sets (e.g. 500+ vendors)

Page-based or lazy loading

Priority: Medium

12. User Feedback & Self-Improving AI (Critical for Product)
12.1 User Feedback Mechanism

Description
Allow users to rate search results.

Feedback types

Result is helpful / not helpful

Missing vendors

Incorrect ranking

Suggested corrections

Priority: High
Intent: Close the human-in-the-loop gap

12.2 AI Self-Reflection & Learning (Future)

Description

Aggregate user feedback

Identify recurring issues

Suggest improvements to:

Ranking logic

Filters

Parsing rules

Note

Does not auto-change logic without approval

Produces insights for admins

Priority: Medium
Intent: Continuous improvement without retraining models