# Reviewer Personas

Reference for multi-persona test review. Each persona reviews the implementation from a specific angle.

## Security Reviewer

**Focus:** Authentication, authorization, injection vulnerabilities, data exposure, secrets management, input validation, OWASP Top 10.

**Prompt template:** "Review the implementation diff for security issues. Focus on: auth boundaries, injection vectors (SQL, command, XSS), data exposure in logs/errors, hardcoded secrets, input validation gaps. For each finding: severity (critical/high/medium), description, recommendation."

## Performance Reviewer

**Focus:** Latency, memory usage, N+1 queries, caching opportunities, algorithmic complexity, resource leaks.

**Prompt template:** "Review the implementation diff for performance issues. Focus on: N+1 query patterns, missing indexes, unbounded loops, memory leaks, missing caching, O(n²) algorithms where O(n) is possible. For each finding: severity, description, recommendation."

## Testing Reviewer

**Focus:** Coverage gaps, edge cases, flaky test patterns, missing error paths, assertion quality.

**Prompt template:** "Review the implementation and test code for testing gaps. Focus on: untested code paths, missing edge cases (null, empty, boundary values), error path coverage, assertion specificity, flaky patterns (timing, ordering). For each finding: severity, description, recommendation."

## Maintainability Reviewer

**Focus:** Coupling, naming clarity, documentation, cyclomatic complexity, dead code, code duplication.

**Prompt template:** "Review the implementation diff for maintainability issues. Focus on: tight coupling, unclear naming, missing documentation for non-obvious logic, high cyclomatic complexity, dead code, duplicated logic. For each finding: severity, description, recommendation."

## Review Output Schema

Each persona returns:
```json
{
  "persona": "security",
  "findings": [
    {
      "severity": "high",
      "description": "SQL injection via unsanitized user input in query builder",
      "recommendation": "Use parameterized queries instead of string concatenation"
    }
  ],
  "verdict": "pass"
}
```

Verdict values: `pass` (no blocking issues), `concern` (issues found but not blocking), `block` (must fix before advancing).

## Deduplication Rules

When merging findings from multiple personas:
- If two personas flag the same issue, keep the higher-severity entry
- Merge recommendations if they complement each other
- Tag merged findings with both persona names
