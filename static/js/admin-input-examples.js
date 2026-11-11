/* Empty-field guidance only: examples never become form values or defaults. */
'use strict';
WorkspacePage.run(({MutationObserver}) => {
  if (!document.body.classList.contains('admin-workspace')) return;

  const common = {
    first_name: 'e.g. Juan', middle_name: 'e.g. Santos', last_name: 'e.g. Dela Cruz',
    full_name: 'e.g. Juan Santos Dela Cruz', attendee_name: 'e.g. Juan Santos Dela Cruz',
    applicant_name: 'e.g. Juan Santos Dela Cruz', member_name: 'e.g. Juan Santos Dela Cruz',
    nationality: 'e.g. Filipino', house_street: 'e.g. 123 Mabini Street',
    address: 'e.g. 123 Mabini Street, Santolan, Pasig City',
    barangay: 'e.g. Santolan', city: 'e.g. Pasig City', region: 'e.g. NCR', zip_code: 'e.g. 1610',
    contact_number: 'e.g. 09171234567', email: 'e.g. juan.delacruz@example.com',
    spouse_name: 'e.g. Maria Dela Cruz', spouse_contact: 'e.g. 09181234567',
    guardian_name: 'e.g. Ana Dela Cruz', guardian_contact: 'e.g. 09191234567',
    emergency_contact_name: 'e.g. Ana Dela Cruz', emergency_contact_number: 'e.g. 09191234567',
    relationship: 'e.g. Parent, spouse or sibling', occupation: 'e.g. Store assistant',
    employer: 'Enter the employer or business name.',
    family_members: 'e.g. 4', household_members: 'e.g. 4', household_monthly_income: 'e.g. 1000',
    pwd_number: 'e.g. 00-0000-000-0000000', philhealth_number: 'e.g. 00-000000000-0',
    voter_certification_number: 'e.g. 123456789',
    control_number: 'Enter the member’s assigned control number.',
    prpwd_lookup_number: 'Enter the number shown in the PRPWD record.',
    slots: 'e.g. 25', capacity: 'e.g. 100',
    instructions: 'Explain what to bring, provide or complete.',
    requirements: 'List the documents or information applicants must provide.',
    photo_instructions: 'Describe the approved photo requirements and assistance available.',
    selection_method: 'Describe the approved EWAF selection process and beneficiary limit.',
    image_alt: 'Describe what the image shows, including any essential text.',
    notes: 'Explain what was done and why.', reason: 'Describe the change and why it is needed.',
    review_notes: 'Summarize the information checked and your findings.',
    decision_notes: 'Explain the decision and the evidence supporting it.',
    change_details: 'Describe which information changed and the correct details.',
    correction_reason: 'Explain which details need correcting and why.',
    feedback: 'Describe what needs attention and the next step.',
    reference: 'Enter the reference printed on the supporting record.',
    authority_reference: 'Enter the reference for the recorded approval.',
    authorized_scope: 'Describe which program and activities the approval covers.',
    signatory: 'Enter the name shown on the signed approval.',
    tie_reason: 'Explain how the approved tie procedure was applied.',
    tie_procedure: 'Describe the procedure authorized for tied applicants.',
    amount: 'Enter the actual cash amount in pesos.',
    estimated_value: 'Enter the recorded non-cash value in pesos.',
    source_office: 'e.g. Barangay Santolan PWD Association',
    subject: 'Write a short, clear subject.', message: 'Explain the request and the information needed.',
    body: 'Write the message and any next steps for the recipient.',
    username: 'e.g. juan.admin', question: 'e.g. How can I apply for membership?',
    answer: 'Explain the steps in clear, simple language.',
    url: 'e.g. https://example.org/information', website: 'e.g. https://example.org',
  };
  const contexts = {
    programs: {
      name: 'e.g. Assistive Device Support',
      description: 'Describe who the program supports and what it provides.',
      benefit: 'e.g. Improve mobility with suitable assistive devices.',
      label: 'e.g. Proof of residency',
    },
    events: {
      title: 'e.g. PWD Community Assembly',
      description: 'Describe the activity, who can attend and what to expect.',
      location: 'e.g. Barangay Santolan covered court',
    },
    announcements: {
      title: 'e.g. Membership Application Schedule',
      content: 'Explain the announcement, relevant dates and what readers need to do.',
    },
    assistance: {
      benefit: 'Describe the assistance actually received, including quantity where relevant.',
      notes: 'Record the receipt details and any relevant remarks.',
    },
  };
  const selector = 'input[name], textarea[name]';
  const types = new Set(['text', 'email', 'tel', 'url', 'number', 'search']);
  const genericHints = new Set(['Enter first name', 'Enter middle name', 'Enter last name',
    'House number and street', 'name@example.com', '0.00']);
  function contextFor(field) {
    const explicit = field.closest('[data-input-examples]')?.dataset.inputExamples;
    if (explicit) return explicit;
    if (field.closest('[data-program-builder]')) return 'programs';
    if (field.closest('[data-event-form]')) return 'events';
    const path = field.form?.getAttribute('action') || location.pathname;
    return Object.keys(contexts).find(name => new RegExp(`/(?:admin/)?${name}(?:/|[-_])`).test(path));
  }
  function apply(field) {
    if (!field.matches(selector) || field.disabled || field.readOnly || field.hasAttribute('data-no-input-example')
        || (field.tagName === 'INPUT' && !types.has(field.type))
        || /password|secret|token|csrf|api[_-]?key/i.test(field.name)
        || (field.getAttribute('placeholder')?.trim() && !genericHints.has(field.getAttribute('placeholder').trim()))) return;
    // Formset prefixes (requirements-0-label, etc.) keep the field's meaning.
    const name = field.name.replace(/^.*-\d+-/, '');
    const context = contextFor(field);
    let example = contexts[context]?.[name] || common[name];
    if (!example && (field.type === 'search' || name === 'q' || name === 'search')) {
      example = 'Search by name or reference…';
    }
    if (!example && field.type === 'email') example = common.email;
    if (!example && field.type === 'tel') example = common.contact_number;
    if (!example && field.type === 'url') example = common.url;
    if (!example) {
      // Keep specific existing instructions when there is no reviewed example.
      const help = (field.getAttribute('aria-describedby') || '').split(/\s+/)
        .filter(id => /helptext|help$|hint/.test(id)).map(id => document.getElementById(id)?.textContent.trim())
        .filter(Boolean).join(' ').replace(/\s+/g, ' ');
      if (help && help.length <= 160) example = help;
    }
    if (!example) {
      const label = [...(field.labels || [])].map(item => item.textContent).join(' ')
        .replace(/\([^)]*\)|\*|:$/g, '').replace(/\s+/g, ' ').trim();
      if (!label || label.length > 70) return;
      example = `Enter ${label.toLowerCase()}.`;
    }
    field.setAttribute('placeholder', example);
  }
  function enhance(root) {
    if (root instanceof Element && root.matches(selector)) apply(root);
    root.querySelectorAll?.(selector).forEach(apply);
  }
  enhance(document);
  // Modal forms, new requirements and saved builder fragments are inserted later.
  new MutationObserver(records => {
    for (const record of records) {
      if (record.type === 'attributes') apply(record.target);
      else record.addedNodes.forEach(enhance);
    }
  }).observe(document.body, {childList: true, subtree: true, attributes: true,
    attributeFilter: ['name', 'disabled', 'readonly', 'type']});
});
