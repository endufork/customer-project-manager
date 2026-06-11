---
name: 项目管理系统
description: 非标设备制造团队的内部项目资料库与工程执行工作台
colors:
  bg: "#f6f7f9"
  surface: "#ffffff"
  surface-soft: "#fbfcfd"
  surface-muted: "#f8fafc"
  line: "#d8dee6"
  line-strong: "#b9c3cf"
  text: "#17202a"
  muted: "#697586"
  accent: "#1f6f5b"
  accent-strong: "#155443"
  blue: "#245a9c"
  warn: "#a15c00"
  warn-bg: "#fff2d8"
  danger: "#b42318"
  danger-strong: "#8f1d14"
typography:
  headline:
    fontFamily: "Microsoft YaHei, Segoe UI, Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "Microsoft YaHei, Segoe UI, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Microsoft YaHei, Segoe UI, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Microsoft YaHei, Segoe UI, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.35
rounded:
  sm: "6px"
  md: "8px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "20px"
  xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "7px 13px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.accent-strong}"
    textColor: "{colors.surface}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "7px 13px"
    height: "36px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "7px 9px"
    height: "36px"
  status-chip:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.muted}"
    rounded: "{rounded.pill}"
    padding: "2px 7px"
---

# Design System: 项目管理系统

## 1. Overview

**Creative North Star: "Operations Ledger"**

This interface is a working ledger for project facts and execution state. It should feel clear, disciplined, and practical: the user is not browsing a product story, they are checking which project needs action, which task is blocked, which file needs confirmation, and what changed.

The system must stay restrained. The design uses light operational surfaces, quiet dividers, compact tables, and a single green accent for committed actions and current selection. The visual language rejects marketing layouts, decorative cards, oversized hero treatment, and attention-seeking color.

**Key Characteristics:**

- Dense but ordered information for repeated daily use.
- Clear separation between project facts and execution process.
- Status and risk are visible through text plus color, never color alone.
- Controls use familiar browser patterns: buttons, tables, dialogs, details, inputs, and selects.
- Destructive and recovery-sensitive actions are visually distinct and never hidden inside ambiguous copy.

## 2. Colors

The palette is a restrained operations palette: neutral surfaces carry the workload, green marks action and selection, blue supports numeric summaries, amber and red mark attention.

### Primary

- **Operational Green**: primary action, active navigation, selected states, and positive workflow progress.
- **Deep Operational Green**: hover and emphasis state for the primary action.

### Secondary

- **Summary Blue**: KPI numbers and low-risk information emphasis.
- **Amber Warning**: blocked, waiting, rework, due-date pressure, and pending WO markers.
- **Safety Red**: delete, reject, and high-risk destructive actions.

### Neutral

- **System Background**: application canvas behind panels.
- **White Surface**: main panels, dialogs, tables, and forms.
- **Soft Surface**: nested task forms, sidebars, subtle grouped regions.
- **Line / Strong Line**: dividers and form borders.
- **Ink Text**: primary readable text.
- **Muted Text**: secondary metadata, hints, timestamps, and counts.

### Named Rules

**The One Accent Rule.** Operational Green is for current selection and committed action only. Do not use it as decoration.

**The Status Pairing Rule.** Every warning, risk, success, or pending state must include text, not just color.

## 3. Typography

**Display Font:** none. This product does not use display typography.

**Body Font:** Microsoft YaHei, Segoe UI, Arial, sans-serif.

**Character:** Familiar system typography supports fast scanning. The type scale is compact and stable; it should never behave like a landing page.

### Hierarchy

- **Headline** (700, 22px, 1.25): application title and major page heading only.
- **Title** (700, 16px, 1.3): panel headings and major section titles.
- **Body** (400, 14px, 1.45): tables, cards, forms, and detail content.
- **Label** (600, 13px, 1.35): field labels, compact controls, secondary headings.
- **Small Metadata** (400-700, 12px): badges, hints, status chips, timestamps.

### Named Rules

**The Fixed Scale Rule.** Product screens use fixed rem/px scale, not fluid hero typography.

**The Scan First Rule.** Numeric identifiers, owners, status, and due dates must remain legible at a glance.

## 4. Elevation

The system is flat by default. Depth is conveyed primarily through borders, tonal surfaces, and layout grouping. Shadows are reserved for top-level surfaces and authentication cards, not repeated list rows or nested panels.

### Shadow Vocabulary

- **Panel Shadow** (`0 8px 24px rgba(20, 31, 43, 0.08)`): top-level page panels only.
- **Auth Shadow** (`0 18px 45px rgba(15, 23, 42, 0.1)`): login card only.

### Named Rules

**The Flat Work Surface Rule.** Task cards, table rows, and filters stay flat. If every item casts a shadow, nothing is important.

## 5. Components

### Buttons

- **Shape:** gently squared controls (6px radius).
- **Primary:** green surface with white text, 36px minimum height, used for create, submit, confirm, and save.
- **Secondary:** white surface, strong neutral border, used for navigation, refresh, open, and utility actions.
- **Danger:** red surface, white text, used only for delete, reject, and irreversible or negative workflow actions.
- **Hover / Focus:** hover darkens or softens the surface. Focus must be visibly stronger than hover and must not rely on color alone.

### Chips

- **Style:** pill-shaped, compact, with text labels.
- **State:** pending, blocked, submitted, completed, risk, and due-date pressure use semantic backgrounds plus readable text.

### Cards / Containers

- **Corner Style:** 6px for repeated items, 8px for major panels.
- **Background:** white for normal items, soft neutral for grouped controls, amber/red tint for blocked or rework states.
- **Shadow Strategy:** no shadow on repeated cards.
- **Border:** 1px neutral border by default.
- **Internal Padding:** 8-12px for dense repeated items, 20-28px for page surfaces.

### Inputs / Fields

- **Style:** white background, strong neutral border, 6px radius, 36px minimum height.
- **Focus:** accent border plus visible focus ring.
- **Disabled:** visibly muted and non-interactive; disabled values should still be readable.

### Navigation

Navigation uses visible text tabs. Active tabs use the primary accent, inactive tabs stay neutral. Do not use icon-only navigation for primary destinations. Project execution can open in a focused window from project detail, but the main navigation tab must switch in the current page.

### Dialogs

Dialogs are for workflow decisions: task creation, risk handling, due-date review, deliverable confirmation. They must have a clear title, close control, explicit primary action, and Esc/backdrop escape.

## 6. Do's and Don'ts

### Do:

- **Do** keep the UI quiet, utilitarian, and work-focused.
- **Do** show the next operational decision first: overdue, blocked, pending confirmation, missing file, or due date.
- **Do** use exact action labels such as "确认关闭", "提交文件", "保存修改", and "删除项目记录".
- **Do** keep destructive actions red and recovery-sensitive.
- **Do** use standard browser controls unless there is a clear workflow reason to build a custom pattern.
- **Do** preserve the separation between project facts and execution process.
- **Do** keep status visible through both label text and color.

### Don't:

- **Don't** make this look like a marketing website, landing page, SaaS hero page, or decorative dashboard.
- **Don't** use oversized hero sections or promotional copy.
- **Don't** use excessive cards, nested cards, decorative shadows, or visual noise.
- **Don't** use bright novelty palettes that distract from project status.
- **Don't** show dense unstructured tables that expose everything at once without priority.
- **Don't** hide critical actions that require PMs or engineers to hunt through multiple layers.
- **Don't** use vague labels such as "OK", "Process", or "Manage" when the action can say exactly what happens.
- **Don't** make engineers fill unnecessary fields before they can update real work state.
