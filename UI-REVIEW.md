# Synapic Desktop UI Review

**Audited:** 2026-07-30
**Application:** Synapic — AI-powered image metadata tagging (Python/CustomTkinter)
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md found)
**Screenshots:** Not captured (desktop GUI application, no dev server)
**Audit Method:** Static code analysis of all step UI modules, background worker, progress tracker, and supporting utilities

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Visual Consistency | 2/4 | Provider tabs serve identical purpose but use disparate layouts, button styles, and save patterns |
| 2. Layout & Hierarchy | 2/4 | Grid overlap bug in Step1; no wizard progress indicator; tab overflow without wrapping |
| 3. Color | 2/4 | Hardcoded hex values throughout (no theme tokens); accent colors inconsistent with each other and with the blue theme |
| 4. Typography | 3/4 | Good hierarchy (Roboto 24 bold -> 16 bold -> 14 -> 12 -> 10) with minor inconsistent usage |
| 5. Spacing | 3/4 | Generally consistent 20px container padding; minor irregularities between frames |
| 6. Interaction Design | 2/4 | No keyboard navigation; no undo; non-standard two-step confirmation; no tooltip help on any control |

**Overall: 14/24**

---

## Top 3 Priority Fixes

1. **Step1 count label grid overlap (app.py Step1 line 101)** — The `lbl_total_count` label is placed at `grid(row=1, column=0, sticky="e", padx=60)` in the same cell as the radio button frame, causing positional overlap when the window is resized. Fix: assign the count label to a separate grid column or use a dedicated row; remove the fragile 60px padx workaround.

2. **Hardcoded color tokens scattered across all step modules** — Hex values like `#2FA572`, `#990000`, `#ffcc00`, `#6b21a8`, `#0ea5e9`, `#2b2b2b`, `#1a1a1a`, `#ff6b35`, `#e05c00`, `#1a73e8`, `#34495e` appear directly in widget constructors. These cannot be updated from a single source, guarantee visual drift, and some (e.g. yellow `#ffcc00` on a blue theme) clash with the declared theme. Fix: define a project-level theme dictionary (or subclass `CTkTheme`) and reference theme keys rather than literal values.

3. **No keyboard navigation or accelerator keys** — Every user action requires a mouse click: navigating between steps, connecting, searching, saving config, scanning, applying dedup. There are no `bind()` entries for common actions (Ctrl+Enter to proceed, Escape to close dialogs, Tab order between controls). Fix: add keyboard bindings for primary actions per step; ensure logical Tab traversal order through form controls.

---

## Detailed Findings

### Pillar 1: Visual Consistency (2/4)

**Strengths:**
- Dark mode applied globally via `ctk.set_appearance_mode("Dark")` in `app.py:133`
- Consistent title format: `font=("Roboto", 24, "bold")` across all 6 step frames
- Same Roboto font family used throughout the entire application
- Good use of separate "Global Settings" card panel (Step2) as an organizational pattern

**BLOCKER — Inconsistent provider tab layouts (Step2Tagging)**

The 5 provider tabs (Groq, Ollama, Nvidia, Google AI, Cerebras) all serve the same purpose — configure API key, select a model, save — yet each uses a different layout pattern:

- **Groq** (`step2_tagging.py:490`): Multi-line textbox for keys, header row with count badge and refresh button, separate scrollable model list with "Available Groq Models" label, status label, selection row, and "Save Config" button
- **Ollama** (`step2_tagging.py:624`): "Info banner" with green background, Host URL + API Key in a two-row config frame, Cloud/Local shortcut buttons, refresh button, status label, image filter checkbox, scrollable model list, selection row, "Save Config" button
- **Nvidia** (`step2_tagging.py:885`): Info banner with dark blue-grey background, single-row key entry with refresh and status, image filter checkbox in a separate grid row, scrollable model list, selection row, "Save Config"
- **Google AI** (`step2_tagging.py:1090`): Info banner with Google blue background, same structure as Nvidia
- **Cerebras** (`step2_tagging.py:1295`): Info banner with Cerebras orange background, same structure as Nvidia

Each provider tab has a different arrangement of the same logical controls. A user switching providers sees a completely different layout each time, creating a poor mental model.

**WARNING — Button style drift**

- "Previous" button: Step2 (line 232) uses `fg_color="gray"`; Step3 (line 134) uses `fg_color="gray"`; StepUpscale (line 213) uses `fg_color="transparent"` with `border_width=1` and explicit `text_color`
- "Disconnect" button (Step1 line 419): `fg_color="#990000"` — hardcoded dark red
- "Back" button (StepDedup line 293): `width=80`, no color customization
- The "Delete" button on cached model items (Step2 line 1648): uses emoji text "delete" with transparent background

**WARNING — Title style inconsistency**

- Step1-4 use format `"Step N: Name"` with Roboto 24 bold
- StepDedup uses `"Duplicate Detection"` with emoji via `ctk.CTkFont(size=24, weight="bold")`
- StepUpscale uses `"Daminion Upscale"` with Roboto 24 bold, no emoji, no step number

---

### Pillar 2: Layout & Hierarchy (2/4)

**Strengths:**
- Every step frame uses `grid_rowconfigure(0, weight=1)` and `grid_columnconfigure(0, weight=1)` for proper resizing
- Scrollable containers for model lists and results areas
- Consistent navigation button placement (bottom of each step)
- Good use of `tkraise()` pattern for step switching without destroying state

**BLOCKER — Grid cell overlap in Step1**

`step1_datasource.py:71-102`:
- Title at `grid(row=0, column=0)` — line 71
- Radio button frame `rb_frame` at `grid(row=1, column=0)` — line 78
- Count label `lbl_total_count` at `grid(row=1, column=0, sticky="e", padx=60)` — line 101

The count label is placed in the exact same grid cell as the radio button frame. The `padx=60` and `sticky="e"` are used as a workaround to push it to the right edge, but this creates positional overlap when the window width changes. At narrower widths (< 1100px minimum), the label will collide with the radio buttons.

**WARNING — No wizard progress indicator**

Users navigating through the 6-step wizard have no visual cue of:
- Which step they are currently on
- How many steps remain
- Which steps they have completed
- The overall workflow sequence

This is a significant orientation gap for a wizard-style interface. Contrast with a typical wizard that shows "Step 2 of 4: Tagging Engine" with a progress bar or step indicators.

**WARNING — Overlapping sections in StepDedup**

When scanning is in progress (`step_dedup.py:496-509`):
- `initial_label` is hidden via `pack_forget()`
- `progress_frame` is shown via `grid(row=2, column=0, ...)` 
- But `initial_label` remains in the scroll frame's memory, and if the user navigates back without scanning, it's re-shown

The progress frame (`progress_frame`) at `grid(row=2, ...)` and the results area (`results_scroll`) at `grid(row=3, ...)` are in adjacent rows with `rowconfigure(3, weight=1)`, meaning when results exist, the progress bar (row 2) takes no extra space but also doesn't have proper weight.

**WARNING — Step2 engine cards overflow**

`step2_tagging.py:75-85`: Engine cards are laid out in a 4-column grid. With 8 providers, this creates 2 full rows. At the minimum window width (1100px), the cards may wrap awkwardly or require horizontal scrolling since the container is inside a `CTkScrollableFrame`.

---

### Pillar 3: Color (2/4)

**Strengths:**
- Dark mode applied globally — good for a photography/image processing application
- Color used meaningfully: green for success states, red for errors, orange for warnings
- Provider-branded info banners help distinguish providers visually

**BLOCKER — Hardcoded hex colors throughout**

The following hardcoded hex values were found, none of which reference a central theme:

| Value | Location | Usage |
|-------|----------|-------|
| `#2FA572` | step2_tagging.py:135, 187, 551, 801, 1781 | Model info color, success text |
| `#ffcc00` | step1_datasource.py:857 | Process Limit label — yellow on blue theme |
| `#990000` | step1_datasource.py:422 | Disconnect button |
| `#6b21a8` | step1_datasource.py:401, step_upscale.py:179 | Dedup/Upscale buttons (purple) |
| `#0ea5e9` | step1_datasource.py:412 | Upscale button (cyan) |
| `#ff6b35` | step2_tagging.py:1722 | HF warning banner (orange) |
| `#e05c00` | step2_tagging.py:1301 | Cerebras info banner |
| `#1a73e8` | step2_tagging.py:1096 | Google AI info banner |
| `#34495e` | step2_tagging.py:891 | Nvidia info banner |
| `#2b2b2b` | step1_datasource.py:105, step2_tagging.py:121, 143 | Canvas/frame backgrounds |
| `#1a1a1a` | step1_datasource.py:384, 790, 795 | Status/limit frame backgrounds |
| `green` | step1_datasource.py:253 | Connect button — this uses CustomTkinter's named green, not the theme blue |

These values cannot be centrally updated. A rebranding or theme change requires editing every file individually.

**WARNING — No 60/30/10 color distribution**

The interface has no structured color system. The dominant color is CustomTkinter's default blue (from `set_default_color_theme("blue")` in `app.py:134`), but:
- Accent colors (green, red, purple, cyan, orange) compete rather than complement
- The 60/30/10 rule (60% dominant, 30% secondary, 10% accent) is not followed
- Yellow `#ffcc00` on the Process Limit slider is unrelated to the blue theme

**WARNING — Color contrast for accessibility**

- Hint/instruction text uses `text_color="gray"` or `text_color="gray70"` — on a `#2b2b2b` background, gray text may fall below WCAG AA contrast ratios (3:1 for large text, 4.5:1 for body text)
- The "Connected" status label uses `text_color="green"` (named color, approximately `#008000`). On a `#1a1a1a` background, this green may have insufficient contrast

---

### Pillar 4: Typography (3/4)

**Strengths:**
- Consistent type ramp: 24pt bold (titles), 16-18pt bold (section headers), 12-14pt (body), 9-11pt (hints/secondary)
- Roboto used throughout as the primary UI font
- Good use of monospace (Courier New) for model lists and log consoles, creating aligned tabular layouts
- Font weight differentiation (bold vs regular) creates clear hierarchy

**WARNING — Inconsistent label types for model display**

Provider tabs use inconsistent label text structures for their model scroll areas:
- Groq: `"Available Groq Models"` as `label_text` on `CTkScrollableFrame` (line 556)
- Ollama: `"Available Ollama Models"` as `label_text` (line 699)
- Nvidia: `"Available Nvidia models"` (lowercase 'm' — line 934)
- Google AI: `"Available Google AI Models"` (line 1140)
- Cerebras: `"Available Cerebras Models"` (line 1351)
- Local: `"Ready for Local Inference"` as `label_text` (line 1550) — different semantic from the others
- OpenRouter: `"OpenRouter Vision Models"` — different format (line 1937)
- HF: `"Recommended Multi-modal Models"` — different format (line 1755)

The capitalization and phrasing differ across tabs that serve identical purposes.

**WARNING — Monospace model list alignment is fragile**

Model list display strings like `f"{mid:<40} | {capability:^15} | {size_str:>10}"` (used in Groq, Ollama, Nvidia, Google AI, Cerebras, Local, OpenRouter, HF tabs) rely on Courier New's fixed character widths for alignment. This works with Courier but will break if the font is ever changed to a proportional typeface. The hardcoded padding values (40, 15, 10) also mean model IDs longer than 40 characters get truncated with ".." rather than handled dynamically.

**WARNING — Warning label font sizes**

- HF rate-limit warning (step2_tagging.py:1729): uses 11pt for an important rate-limit notice that affects workflow planning. Should be at least 13pt to draw attention.
- Action warning for "Delete from Disk" (step_dedup.py:362): uses 10pt. A destructive irreversible action warning should be more prominent.

---

### Pillar 5: Spacing (3/4)

**Strengths:**
- Container padding consistently uses `padx=20, pady=20` across all steps
- Internal sections use consistent 10px spacing between related elements
- Navigation button areas consistently use `pady=20`
- Model list items use consistent `pady=2` spacing

**WARNING — Inconsistent internal padding**

| Location | padx/pady | Notes |
|----------|-----------|-------|
| Step1 container | padx=20, pady=20 (line 63) | Standard |
| Step2 container | padx=20, pady=20 (line 62) | Standard |
| Step3 container | padx=20, pady=20 (line 46) | Standard |
| Step1 canvas area | padx=(20,5), pady=20 (line 121) | Left/right asymmetry |
| Step1 Daminion labels | grid_kws padx=20, pady=5 (line 210) | Tighter vertical |
| Step1 resize hint | padx=24 (line 841) | Non-standard |
| Step2 header row | padx=10 (line 503) | Tighter than container |
| StepDedup settings | padx=(15,10), padx=10, padx=(10,15) (lines 311-368) | Varying per column |

**WARNING — No responsive spacing strategy**

The application uses fixed pixel values throughout. At the minimum window size (1100x760), some spacing becomes tight. There is no proportional spacing (using weight-based column sizing) for internal padding — only the main grid uses `weight=1`.

**WARNING — Model list item spacing**

Model list items use `pady=2` spacing (e.g., step2_tagging.py:484, 822). With many models, this can feel cramped. Consider `pady=4` for better visual breathing room, especially since each item is a clickable button.

---

### Pillar 6: Interaction Design (2/4)

**Strengths:**
- Excellent threading model: all blocking operations (API calls, model downloading, scanning) run on background threads via `BackgroundWorker` or explicit threading
- Debouncing on search inputs via `submit_replacing()` — prevents API hammering during typing
- Button state management: disabling start/stop/navigation during processing is correct and consistent
- Graceful shutdown: each step implements `shutdown()` for clean resource cleanup
- Confirmation for destructive dedup actions (two-step "Confirm to proceed" pattern)
- `DaminionDedupProcessor.abort()` allows cancellation of in-progress scans

**BLOCKER — No keyboard navigation**

The entire application is mouse-driven. There are no:
- Keyboard shortcuts for common actions (Ctrl+Enter to submit, Escape to close, Ctrl+N for new session)
- Tab traversal order configured between form fields
- Focus management (focus doesn't automatically move to the first input when a step loads)
- Enter key submission on dialogs

This affects both power users (speed of operation) and accessibility.

**BLOCKER — No undo for any action**

- Deleting a cached model (step2_tagging.py:1658-1675): Shows a confirmation dialog, but once confirmed, the model directory is permanently deleted via `shutil.rmtree()`. No trash/recycle bin pattern.
- Applying deduplication: Once "Confirm to proceed" is clicked, the action is irreversible. The dedup apply pattern does show a progress bar and result summary, but there is no "Undo" after completion.
- The "New Session" button in Step4Results simply navigates to Step1 without confirmation and without clearing results — but there's no "Go Back to Results" path after clicking it.

**WARNING — Non-standard two-step confirmation pattern**

The dedup apply button uses a two-step confirmation (`step_dedup.py:690-703`):
1. First click: button text changes to "Confirm to proceed" and turns red
2. Second click: action executes

This is not a standard UI pattern. Users may:
- Not notice the button text changed (they clicked "Apply Deduplication" but now it says "Confirm to proceed")
- Get confused when the button turns red — this typically indicates an error state
- Accidentally trigger a destructive action on the second click because the visual change wasn't registered

A standard confirm dialog (messagebox.askyesno with explicit "Delete/Cancel" buttons) would be more recognizable.

**WARNING — No tooltip/hover help on any control**

- The AI inference scale options in Step1 (100%, 75%, 50%, 25%) have no explanation of what the scale does beyond the italic hint below
- Dedup algorithm options (phash, dhash, ahash, whash) have no tooltip explaining the differences
- The "Auto-paginate" checkbox in Step3 has no explanation of when to enable/disable it
- API key fields don't indicate where to obtain an API key (though some provider banners do include URLs)

**WARNING — No confirmation for navigation away from Step2**

If a user has configured engine settings but not clicked "Save Config" (per-provider), clicking "Next Step" silently navigates to Step3 without saving. The `next_step()` method (step2_tagging.py:326-339) only sets `engine.provider` — all other config changes are discarded unless the user clicked the specific per-provider "Save Config" button. This is a significant data loss risk.

**WARNING — Dialogue dismissal inconsistency**

- `messagebox.showinfo/warning/error` blocks until the user clicks OK — this is standard
- `DownloadManagerDialog` uses `grab_set()` (line 2118) making it modal, but only sets `self.transient(parent)` without `self.focus_set()` — the dialog may appear behind the parent window
- Connection failure in Step1 shows `messagebox.showerror` — but the error message is generic ("Could not connect to Daminion server. Check URL and credentials.") rather than surfacing the actual server error

---

## Files Audited

- `src/ui/app.py` (276 lines) — Main window, session lifecycle, wizard coordinator
- `src/ui/steps/step1_datasource.py` (1271 lines) — Data source selection (local + Daminion)
- `src/ui/steps/step2_tagging.py` (2488 lines) — Engine configuration (8 providers, download manager)
- `src/ui/steps/step3_process.py` (243 lines) — Processing execution and monitoring
- `src/ui/steps/step4_results.py` (177 lines) — Results review and metrics dashboard
- `src/ui/steps/step_dedup.py` (986 lines) — Duplicate detection and management
- `src/ui/steps/step_upscale.py` (767 lines) — Image upscaling batch processor
- `src/main.py` — Application entry point
- `src/utils/background_worker.py` (266 lines) — Thread-safe task queue worker
- `src/core/enhanced_progress.py` (410 lines) — Multi-stage progress tracking
- `src/utils/logger.py` (612 lines) — Logging with sensitive data masking
- `src/utils/registry_config.py` (189 lines) — Windows Registry credential/preference storage
- `src/ui/steps/__init__.py` — Step module exports

---

## Additional Recommendations (Non-Blocking)

1. **Add wizard step indicators.** A sidebar, top tab bar, or breadcrumb showing "Step 1/6: Datasource -> Step 2/6: Tagging -> ..." would provide critical orientation context. This is standard wizard UX.

2. **Consolidate provider tab layouts.** Extract a shared pattern for provider configuration: info banner -> API key row -> model filter -> model list -> selection row -> save button. Each provider tab should use the same template with different data.

3. **Add a visual empty state for processing.** Step3 shows "Ready to start." when idle — consider showing the session summary (items to process, engine selected) as a pre-flight check before the user clicks Start.

4. **Make the count label update visible.** In Step1, `lbl_total_count` (the "Records found: X" label) uses italic gray text. This is easily missed. Consider a brief highlight animation when the count updates.

5. **Add confirmation before "New Session" (Step4Results).** The current implementation silently navigates back to Step1. If there are results from a completed session, the user should be asked whether they want to discard them.

6. **Standardize the "Back"/"Previous" button.** Currently varies between gray solid, gray transparent, and transparent-with-border. Pick one style and use it everywhere.

7. **Add warning-level color to the Process Limit slider.** The yellow `#ffcc00` label on the process limit slider could be orange-red when close to the limit (e.g., >90% of available records selected for processing).

8. **Consider a light mode option.** While dark mode is appropriate for a photography tool, the `set_appearance_mode("Dark")` call in `app.py:133` hardcodes the mode. A toggle in settings or an OS-aware preference would be more user-friendly.
