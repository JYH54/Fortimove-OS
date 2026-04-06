# Review Console Operator Guide

**Quick Start Guide for Product Review Operators**

---

## Access the Review Console

**Review List:** http://localhost:8000/review/list

---

## Review List Page

### What You See
- **Review ID:** Unique identifier for each review
- **Product Title:** Name of the product being reviewed
- **Score:** AI-generated quality score (0-100)
- **Decision:** AI recommendation (PASS, HOLD, REJECT)
- **Status:** Current review status (draft, under_review, approved_for_export, etc.)
- **Primary Image:** Whether a primary image is set (⭐)
- **Export Ready:** Whether the review can be exported (✅/❌)
- **Updated:** Last modification timestamp

### Actions
- **Filter by Status:** Use dropdown to filter reviews (draft, under_review, approved, hold, rejected)
- **Search:** Type product name or review ID to search
- **Click "Review":** Opens the review detail page for editing

---

## Review Detail Page

### Layout Overview

```
┌─────────────────────────────────────────────────────────────┐
│  LEFT SIDE: Generated (READ-ONLY)                           │
│  - AI-generated content                                     │
│  - Gray background                                          │
│  - Cannot be edited directly                                │
│                                                             │
│  RIGHT SIDE: Reviewed (EDITABLE)                            │
│  - Your edits and modifications                             │
│  - White background                                         │
│  - Fully editable                                           │
│                                                             │
│  BOTTOM: Image Review Panel                                 │
│  - Click image to set as primary                            │
│  - Click ❌/✅ to exclude/restore                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Editing Workflow

### Step 1: Review Generated Content (Left Side)
- **DO NOT TRY TO EDIT** - These fields are read-only
- Review the AI-generated titles, descriptions, tags, and price
- Check for quality, accuracy, and compliance issues

### Step 2: Edit Reviewed Content (Right Side)
If the generated content needs changes:

1. **Naver Title:** Edit the title for Naver marketplace
2. **Naver Description:** Edit the product description
3. **Naver Tags:** Edit tags (comma-separated)
4. **Coupang Title:** Edit the title for Coupang marketplace
5. **Coupang Description:** Edit the product description
6. **Price:** Adjust the selling price
7. **Review Notes:** Add any internal notes or reasons for changes

**If generated content is good:** Leave reviewed fields empty - they will automatically use generated content as fallback.

### Step 3: Save Draft
Click **"Save Draft"** button to save your edits without changing the review status.

You can return later to continue editing.

---

## Image Review

### Setting Primary Image
1. Click on any image in the image panel
2. The clicked image becomes the primary image
3. Previous primary image is automatically unset
4. Primary image shown with **⭐ PRIMARY** badge

### Excluding Images
1. Click the **❌** or **✅** badge on any image
2. **❌ = Excluded** - Image will not be exported (dimmed, red border)
3. **✅ = Included** - Image will be exported (normal appearance)

**Important Rules:**
- ⚠️ **Cannot set excluded image as primary**
- ⚠️ **At least one non-excluded image required for export**
- ⚠️ **Only one primary image allowed**

---

## Workflow Actions

### Save Draft
- **When to use:** You need more time to review or edit
- **Effect:** Saves your changes, status remains "draft"
- **Can return:** Yes, you can come back later

### Hold
- **When to use:** Need more information or clarification
- **Effect:** Status changes to "hold"
- **Can resume:** Yes, status can be changed back to "draft" later

### Reject
- **When to use:** Product has serious quality or compliance issues
- **Effect:** Status changes to "rejected" (terminal state)
- **Can reverse:** ⚠️ No, rejection is final

### Approve for Export
- **When to use:** Product passed review and ready for marketplace
- **Effect:** Status changes to "approved_for_export"
- **Export enabled:** Yes, CSV export buttons become active

---

## CSV Export

### When Available
Export buttons are **only enabled** after status is "approved_for_export" or "approved_for_upload".

### How to Export
1. Click **"Export Naver CSV"** or **"Export Coupang CSV"**
2. CSV file downloads automatically
3. Export log is recorded in database

### Export Rules
- **reviewed_* fields used first** - Your edits take priority
- **generated_* fields as fallback** - Used if you didn't edit
- **Non-excluded images only** - Excluded images are not exported
- **Primary image first** - Or first non-excluded by order

---

## Status Workflow

```
draft
  └─→ under_review (after initial save/submit)
        ├─→ approved_for_export ✅ (ready for marketplace)
        ├─→ approved_for_upload ✅ (ready for direct upload)
        ├─→ hold (need more info)
        └─→ rejected ❌ (terminal, cannot reverse)

hold
  └─→ draft (can reopen for continued review)
```

### Status Meanings
- **draft:** Initial state, not yet reviewed
- **under_review:** Currently being reviewed by operator
- **approved_for_export:** Passed review, ready for CSV export
- **approved_for_upload:** Passed review, ready for direct upload
- **hold:** On hold, need more information
- **rejected:** Rejected, will not be exported (terminal)

---

## Common Tasks

### Task: Quick Approve (No Edits Needed)
1. Open review detail
2. Check generated content (left side) - looks good
3. Verify images - set primary if needed
4. Click **"Approve for Export"**
5. Done! Export buttons now active

### Task: Edit and Approve
1. Open review detail
2. Review generated content (left side)
3. Edit reviewed fields (right side) as needed
4. Click **"Save Draft"** to save edits
5. Review images, set primary, exclude bad images
6. Click **"Approve for Export"**
7. Export CSV when ready

### Task: Hold for Clarification
1. Open review detail
2. Add notes in "Review Notes" field explaining what's needed
3. Click **"Save Draft"**
4. Click **"Hold"**
5. Return later after clarification received

### Task: Reject Product
1. Open review detail
2. Add notes in "Review Notes" field explaining rejection reason
3. Click **"Reject"**
4. ⚠️ **Warning:** This is final, cannot be undone

---

## Error Messages

### "Cannot set excluded image as primary"
**Problem:** You tried to set an excluded image as primary
**Solution:** First restore the image (click ✅), then set as primary

### "No exportable images found"
**Problem:** All images are excluded
**Solution:** Restore at least one image by clicking ✅

### "Status not approved for export"
**Problem:** Review status is not "approved_for_export" or "approved_for_upload"
**Solution:** Complete review and click "Approve for Export" first

### "Invalid status transition"
**Problem:** You tried to change status in an invalid way (e.g., draft → approved directly)
**Solution:** Follow proper workflow: draft → under_review → approved

---

## Best Practices

### ✅ DO
- Review generated content carefully for accuracy and compliance
- Add clear notes when holding or rejecting reviews
- Set a clear primary image that represents the product well
- Exclude low-quality, irrelevant, or duplicate images
- Save drafts frequently to avoid losing work

### ❌ DON'T
- Don't try to edit generated content fields (left side) - they're read-only
- Don't reject without adding clear notes explaining why
- Don't set excluded images as primary
- Don't exclude all images - at least one needed for export
- Don't rush - quality review is important for marketplace success

---

## Keyboard Shortcuts

*None currently - future enhancement*

---

## Troubleshooting

### "Page won't load"
- Check your internet connection
- Refresh the page (F5)
- Check if server is running

### "Changes not saving"
- Click "Save Draft" button after making edits
- Check for error messages at bottom of page
- Refresh and try again

### "Export buttons disabled"
- Check review status - must be "approved_for_export" or "approved_for_upload"
- Click "Approve for Export" first
- Ensure at least one non-excluded image exists

### "Can't find a review"
- Use search bar at top of review list
- Check status filter - review may be filtered out
- Try "All" status filter to see all reviews

---

## Support

**Technical Issues:** Contact development team
**Product Questions:** Contact product manager
**Process Questions:** Refer to this guide or contact supervisor

---

**Last Updated:** 2026-03-31
**Version:** 1.0 (Phase 4 Release)
