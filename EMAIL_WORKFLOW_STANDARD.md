# Email Workflow Standardization

This document outlines the standardized email sending workflow used throughout the AI Teaching Companion application.

## Overview

All email sending functionality follows a consistent two-step "Generate Preview → Review/Edit → Send" pattern that enhances user control and prevents accidental sends.

## Standard Components

### 1. HTML Structure

Every page with email functionality must include these three modal components:

#### A. Loading Overlay
```html
<!-- Loading overlay -->
<div
  id="email-loading-overlay"
  class="fixed inset-0 z-40 hidden bg-slate-900/40 backdrop-blur-sm items-center justify-center">
  <div class="bg-white/95 rounded-2xl shadow-xl border border-slate-200 px-6 py-5 flex items-center gap-4">
    <div class="h-9 w-9 rounded-full border-4 border-emerald-100 border-t-emerald-500 animate-spin"></div>
    <div class="text-left">
      <p class="text-sm font-semibold text-emerald-700">Processing your email…</p>
      <p class="text-xs text-slate-500 mt-1">This usually takes just a few seconds.</p>
    </div>
  </div>
</div>
```

#### B. Feedback Popup
```html
<!-- Feedback popup -->
<div
  id="email-feedback"
  class="fixed inset-0 z-40 hidden bg-slate-900/40 backdrop-blur-sm items-center justify-center">
  <div
    id="email-feedback-card"
    class="bg-white rounded-2xl shadow-xl border px-6 py-6 max-w-sm w-full mx-4 flex items-start gap-4 min-h-[6rem]">
    <div id="email-feedback-icon" class="mt-0.5 shrink-0"></div>
    <div class="flex-1">
      <h3 id="email-feedback-title" class="text-sm font-semibold"></h3>
      <p id="email-feedback-message" class="mt-1 text-xs text-slate-600"></p>
      <div class="mt-3 flex justify-end">
        <button
          type="button"
          id="email-feedback-close"
          class="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium
                 bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors">
          Close
        </button>
      </div>
    </div>
  </div>
</div>
```

#### C. Email Preview/Edit Modal
```html
<!-- Email Preview/Edit Modal -->
<div id="preview-modal" class="fixed inset-0 z-[60] hidden" role="dialog" aria-modal="true">
  <div class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"></div>
  
  <div class="fixed inset-0 z-10 overflow-y-auto">
    <div class="flex min-h-full items-center justify-center p-4 text-center sm:p-0">
      <div class="relative transform overflow-hidden rounded-xl bg-white text-left shadow-2xl transition-all sm:my-8 sm:w-full sm:max-w-3xl border border-slate-200">
        <!-- Header -->
        <div class="bg-emerald-50 px-6 py-4 border-b border-emerald-100 flex items-center justify-between">
          <h3 class="text-lg font-semibold text-emerald-900 flex items-center gap-2">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
            </svg>
            Review & Edit Email
          </h3>
          <button id="preview-close" class="text-slate-400 hover:text-slate-600 rounded-md p-1 hover:bg-emerald-100 transition-colors">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Email Preview/Edit Form -->
        <div class="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          <div class="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-start gap-3">
            <svg class="w-5 h-5 text-emerald-600 mt-0.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
            </svg>
            <div class="flex-1">
              <p class="text-sm text-emerald-900 font-medium">AI-Generated Email Preview</p>
              <p class="text-xs text-emerald-700 mt-1">
                Feel free to edit the generated email. Your edited content will be used exactly as written.
              </p>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">To</label>
            <input id="preview-to" type="email" readonly
              class="block w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600" />
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">Subject</label>
            <input id="preview-subject" type="text"
              class="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/60" />
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">Email Body</label>
            <textarea id="preview-body" rows="14"
              class="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/60 resize-y font-mono"></textarea>
            <p class="mt-2 text-xs text-slate-500">
              <svg class="w-3 h-3 inline text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" />
              </svg>
              This is the final email content that will be sent/saved.
            </p>
          </div>
        </div>

        <!-- Footer with Actions -->
        <div class="bg-slate-50 px-6 py-4 border-t border-slate-200">
          <div class="flex flex-col gap-3">
            <!-- Status and View Drafts Section -->
            <div id="preview-status-section">
              <div id="preview-status" class="text-sm font-medium text-emerald-600 mb-3 hidden"></div>
              <a id="preview-view-drafts" href="https://mail.google.com/mail/u/0/#drafts" target="_blank"
                class="hidden inline-flex items-center gap-1.5 text-sm font-medium text-emerald-600 hover:text-emerald-700 transition-colors mb-3">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                </svg>
                <span class="underline">View Drafts in Gmail</span>
                <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
                </svg>
              </a>
            </div>

            <!-- Action Buttons -->
            <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-3">
              <button type="button" id="preview-cancel"
                class="inline-flex items-center justify-center px-4 py-2 border border-slate-300 shadow-sm text-sm font-medium rounded-md text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500">
                Cancel
              </button>
              <button type="button" id="preview-save-draft"
                class="inline-flex items-center justify-center px-4 py-2 border border-emerald-300 shadow-sm text-sm font-medium rounded-md text-emerald-700 bg-emerald-50 hover:bg-emerald-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 transition-all">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M17 16v2a2 2 0 01-2 2H5a2 2 0 01-2-2v-7a2 2 0 012-2h2m3-4H9a2 2 0 00-2 2v7a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-1m-1 4l-3 3m0 0l-3-3m3 3V3" />
                </svg>
                Save as Draft
              </button>
              <button type="button" id="preview-send"
                class="inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-emerald-600 hover:bg-emerald-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 transition-all">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                </svg>
                Send Email
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 2. JavaScript Helper Functions

Every page must include these helper functions:

```javascript
const loadingOverlay = document.getElementById("email-loading-overlay");
const feedback = document.getElementById("email-feedback");
const feedbackCard = document.getElementById("email-feedback-card");
const feedbackIcon = document.getElementById("email-feedback-icon");
const feedbackTitle = document.getElementById("email-feedback-title");
const feedbackMessage = document.getElementById("email-feedback-message");
const feedbackClose = document.getElementById("email-feedback-close");

// Preview modal elements
const previewModal = document.getElementById("preview-modal");
const previewClose = document.getElementById("preview-close");
const previewCancel = document.getElementById("preview-cancel");
const previewTo = document.getElementById("preview-to");
const previewSubject = document.getElementById("preview-subject");
const previewBody = document.getElementById("preview-body");
const previewSaveDraft = document.getElementById("preview-save-draft");
const previewSend = document.getElementById("preview-send");
const previewStatus = document.getElementById("preview-status");
const previewViewDrafts = document.getElementById("preview-view-drafts");

// Store form data for later use
let currentFormData = {
  cc: "",
  bcc: "",
  tone: ""
};

function showLoading() {
  loadingOverlay.classList.remove("hidden");
  loadingOverlay.classList.add("flex");
}

function hideLoading() {
  loadingOverlay.classList.add("hidden");
  loadingOverlay.classList.remove("flex");
}

function closePreviewModal() {
  previewModal.classList.add("hidden");
  previewStatus.classList.add("hidden");
  previewViewDrafts.classList.add("hidden");
}

function showFeedback(type, title, message) {
  if (type === "success") {
    feedbackCard.className =
      "bg-white rounded-2xl shadow-xl border border-green-200 px-6 py-6 max-w-sm w-full mx-4 flex items-start gap-4 min-h-[6rem]";
    feedbackIcon.innerHTML =
      `<svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
         <path stroke-linecap="round" stroke-linejoin="round"
               d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
       </svg>`;
    feedbackTitle.className = "text-sm font-semibold text-green-800";
  } else {
    feedbackCard.className =
      "bg-white rounded-2xl shadow-xl border border-red-200 px-6 py-6 max-w-sm w-full mx-4 flex items-start gap-4 min-h-[6rem]";
    feedbackIcon.innerHTML =
      `<svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
         <path stroke-linecap="round" stroke-linejoin="round"
               d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
       </svg>`;
    feedbackTitle.className = "text-sm font-semibold text-red-800";
  }
  feedbackTitle.textContent = title;
  feedbackMessage.textContent = message;
  feedback.classList.remove("hidden");
  feedback.classList.add("flex");
}

function hideFeedback() {
  feedback.classList.add("hidden");
  feedback.classList.remove("flex");
}

if (feedbackClose) {
  feedbackClose.addEventListener("click", hideFeedback);
}
feedback?.addEventListener("click", (e) => {
  if (e.target === feedback) hideFeedback();
});

previewClose?.addEventListener("click", closePreviewModal);
previewCancel?.addEventListener("click", closePreviewModal);
```

### 3. Email Workflow Implementation

#### Step 1: Generate Preview

When the user clicks "Generate Preview" button:

```javascript
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  showLoading();
  submitBtn.disabled = true;

  const formData = new FormData(form);
  formData.set('action', 'draft'); // Always generate as draft for preview

  // Store form data for later
  currentFormData = {
    cc: formData.get('cc') || "",
    bcc: formData.get('bcc') || "",
    tone: formData.get('tone') || "professional, friendly"
  };

  try {
    const res = await fetch("{{ url_for('email.email_compose') }}", { 
      method: "POST", 
      body: formData 
    });
    const json = await res.json().catch(() => ({ error: "Invalid response" }));

    hideLoading();

    if (res.ok && !json.error) {
      // Populate preview modal
      previewTo.value = formData.get('to_email');
      previewSubject.value = formData.get('subject') || json.subject || "";
      
      // Extract email body
      let emailBody = "";
      if (json.preview && json.preview.plain) {
        emailBody = json.preview.plain;
      } else if (json.body) {
        emailBody = json.body;
      } else if (json.content) {
        emailBody = json.content;
      } else if (json.message) {
        emailBody = json.message;
      }
      
      previewBody.value = emailBody;

      // Show preview modal
      previewModal.classList.remove("hidden");
    } else {
      showFeedback("error", "Unable to generate preview", 
        json.error || "Something went wrong.");
    }
  } catch (err) {
    hideLoading();
    showFeedback("error", "Network error", 
      err.message || "Problem connecting to server.");
  } finally {
    submitBtn.disabled = false;
  }
});
```

#### Step 2: Save as Draft from Preview

```javascript
previewSaveDraft.addEventListener("click", async () => {
  previewSaveDraft.disabled = true;
  previewSend.disabled = true;
  previewStatus.textContent = "Saving draft...";
  previewStatus.className = "text-sm font-medium text-emerald-600 animate-pulse";
  previewStatus.classList.remove("hidden");

  try {
    const editedContent = previewBody.value.trim();
    const instruction = `IMPORTANT: Use the following email content EXACTLY as written. Do not modify, rephrase, or regenerate. This is the final approved content:\n\n${editedContent}`;

    const formData = new FormData();
    formData.append("to_email", previewTo.value);
    formData.append("subject", previewSubject.value);
    formData.append("notes", instruction);
    formData.append("tone", "use exact content without any modifications");
    formData.append("action", "draft");
    formData.append("cc", currentFormData.cc);
    formData.append("bcc", currentFormData.bcc);

    const res = await fetch("{{ url_for('email.email_compose') }}", { 
      method: "POST", 
      body: formData 
    });
    const json = await res.json().catch(() => ({ error: "Invalid response" }));

    if (res.ok && json.ok !== false) {
      previewStatus.textContent = "Draft saved successfully in Gmail!";
      previewStatus.className = "text-sm font-medium text-green-600";
      previewViewDrafts.classList.remove("hidden");
    } else {
      previewStatus.textContent = "Error: " + (json.error || "Failed to save draft");
      previewStatus.className = "text-sm font-medium text-red-600";
    }
  } catch (err) {
    previewStatus.textContent = "Error: " + (err.message || "Network error");
    previewStatus.className = "text-sm font-medium text-red-600";
  } finally {
    previewSaveDraft.disabled = false;
    previewSend.disabled = false;
  }
});
```

#### Step 3: Send Email from Preview

```javascript
previewSend.addEventListener("click", async () => {
  previewSaveDraft.disabled = true;
  previewSend.disabled = true;
  previewStatus.textContent = "Sending email...";
  previewStatus.className = "text-sm font-medium text-emerald-600 animate-pulse";
  previewStatus.classList.remove("hidden");

  try {
    const editedContent = previewBody.value.trim();
    const instruction = `IMPORTANT: Use the following email content EXACTLY as written. Do not modify, rephrase, or regenerate. This is the final approved content:\n\n${editedContent}`;

    const formData = new FormData();
    formData.append("to_email", previewTo.value);
    formData.append("subject", previewSubject.value);
    formData.append("notes", instruction);
    formData.append("tone", "use exact content without any modifications");
    formData.append("action", "send");
    formData.append("cc", currentFormData.cc);
    formData.append("bcc", currentFormData.bcc);

    const res = await fetch("{{ url_for('email.email_compose') }}", { 
      method: "POST", 
      body: formData 
    });
    const json = await res.json().catch(() => ({ error: "Invalid response" }));

    if (res.ok && json.ok !== false) {
      previewStatus.textContent = "Email sent successfully!";
      previewStatus.className = "text-sm font-medium text-green-600";
      setTimeout(() => {
        closePreviewModal();
        form.reset();
      }, 1500);
    } else {
      previewStatus.textContent = "Error: " + (json.error || "Failed to send email");
      previewStatus.className = "text-sm font-medium text-red-600";
    }
  } catch (err) {
    previewStatus.textContent = "Error: " + (err.message || "Network error");
    previewStatus.className = "text-sm font-medium text-red-600";
  } finally {
    previewSaveDraft.disabled = false;
    previewSend.disabled = false;
  }
});
```

## Standardized Files

The following files currently implement this standard workflow:

1. ✅ `email.html` - Main email composition page
2. ✅ `assessments_list.html` - Send assessments to batches
3. ✅ `assessment_detail.html` - Send individual student emails
4. ✅ `batch_students.html` - Send emails to students in a batch

## Benefits of This Standardization

1. **Consistent UX**: Users experience the same email workflow across all features
2. **Error Prevention**: Preview step prevents accidental sends
3. **Content Control**: Users can edit AI-generated content before sending
4. **Visual Feedback**: Clear loading states and success/error messages
5. **Maintainability**: Centralized patterns make updates easier
6. **Accessibility**: Consistent modal patterns improve screen reader support

## Adding Email Functionality to New Pages

When adding email functionality to a new page:

1. Copy the three HTML modal components (loading overlay, feedback popup, preview modal)
2. Copy the JavaScript helper functions
3. Implement the three-step workflow (generate → save draft → send)
4. Test all scenarios: success, error, validation, cancellation
5. Update this documentation with the new file

## Future Improvements

- Consider extracting modals into reusable Jinja2 macros
- Create a shared JavaScript module for email functions
- Add unit tests for email workflow
- Implement email templates for common scenarios

