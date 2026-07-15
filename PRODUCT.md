# Product

## Register

product

## Users

This is an internal project management system for a non-standard equipment manufacturing supplier. Primary users are PMs, engineers, and admins.

PMs use the system to create and coordinate project work, track due dates, review deliverables, confirm task completion, handle risks, and keep project execution moving.

Engineers use the system to see assigned work, submit deliverables or completion notes, request due date changes, mark blocked work, create or resolve risks, and keep project facts tied to the project archive.

Admins manage users, roles, configuration, and deletion or recovery-sensitive operations. The current team-trial scope does not include a separate read-only role; it can be reconsidered when a real management-viewer use case exists.

## Product Purpose

The product exists to make customer project execution clear, traceable, and closed-loop. It links the physical project archive, INQ/WO identifiers, tasks, due dates, deliverables, risks, approvals, and execution logs into one local network tool.

Success means PMs and engineers can quickly answer:

- What project or WO is this?
- Who owns the next action?
- What is due and when?
- What is blocked and why?
- What needs PM approval?
- Which files have been submitted or archived?
- What changed, when, and by whom?

The project archive remains the factual base for customer, factory, product, project, INQ/WO, folders, and files. The engineering workbench manages the execution process: tasks, owners, due dates, deliverables, risks, confirmations, and logs.

## Brand Personality

Clear, disciplined, practical.

The interface should feel like a focused internal operations tool for repeated daily use. It should reduce ambiguity and cognitive load rather than impress with decorative styling. The tone is direct and specific: show the next action, the owner, the date, the risk, and the required confirmation.

## Anti-references

Do not make this look like a marketing website, landing page, SaaS hero page, or decorative dashboard.

Avoid:

- Oversized hero sections or promotional copy.
- Excessive cards, nested cards, decorative shadows, or visual noise.
- Bright novelty palettes that distract from project status.
- Dense unstructured tables that show everything at once.
- Hidden critical actions that require PMs or engineers to hunt through multiple layers.
- Vague labels such as "OK", "Process", or "Manage" when the action can say exactly what happens.
- UI that makes engineers fill unnecessary fields before they can update real work state.

## Design Principles

1. Show the next operational decision first.
   Every screen should make it clear what needs attention now: overdue work, blocked tasks, pending approvals, unresolved risks, or missing deliverables.

2. Separate project facts from execution process.
   The project library owns customer, product, INQ/WO, folder, and file facts. The workbench owns tasks, risk, due date changes, deliverables, approvals, and activity logs.

3. Make workflow state explicit.
   A task, risk, due date request, or deliverable should always have a clear status, owner, date, and next possible action.

4. Minimize engineer burden.
   Engineers should not need to understand system bookkeeping. If a task is blocked, the system creates the linked risk. If a file is required, the upload path should make the submission and PM review path obvious.

5. Preserve traceability.
   Changes to due dates, risks, deliverables, task status, and approvals should leave a clear activity record. Destructive actions should be restricted and recoverable.

## Accessibility & Inclusion

The default target is practical WCAG AA behavior for internal tools:

- Body text and muted text must remain readable on light surfaces.
- Status color must be reinforced with text, not color alone.
- Keyboard focus should remain visible on forms, buttons, dialogs, and table rows.
- Dialogs should have clear titles and close controls.
- Motion should be minimal and should not hide content.
- Layout must work on common desktop widths first, with responsive behavior for narrower screens where practical.
