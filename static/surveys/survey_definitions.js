// SurveyJS JSON definitions for the MindFort study
// Three surveys: Informed Consent, Pre-Exposure Measures, Post-Exposure Measures

const LIKERT_7_COLUMNS = [
  { value: 1, text: "1" },
  { value: 2, text: "2" },
  { value: 3, text: "3" },
  { value: 4, text: "4" },
  { value: 5, text: "5" },
  { value: 6, text: "6" },
  { value: 7, text: "7" }
];

// ---------------------------------------------------------------------------
// 1. Informed Consent Survey
// ---------------------------------------------------------------------------
window.consentSurvey = {
  showQuestionNumbers: "on",
  pages: [
    {
      name: "consent_page",
      elements: [
        {
          type: "html",
          name: "consent_info",
          html: "<h3>Informed Consent</h3>" +
            "<p>Thank you for your interest in this study conducted by researchers at the <strong>University of Oulu</strong>.</p>" +
            "<p><strong>Study description:</strong> You will read a simulated conversation about binge drinking and answer questions before and after.</p>" +
            "<p><strong>Duration:</strong> Approximately 10 minutes.</p>" +
            "<p><strong>Data handling:</strong> Your responses are anonymous and linked only to your Prolific ID. No personally identifiable information will be collected beyond what Prolific provides.</p>" +
            "<p><strong>Voluntary participation:</strong> Your participation is entirely voluntary. You have the right to withdraw at any time without penalty or loss of compensation.</p>" +
            "<p>If you have any questions about this study, please contact the research team at the University of Oulu.</p>"
        },
        {
          type: "checkbox",
          name: "consent",
          title: "Consent to participate",
          isRequired: true,
          choices: [
            { value: "agreed", text: "I have read and agree to participate" }
          ],
          validators: [
            {
              type: "answercount",
              minCount: 1,
              text: "You must agree to participate before continuing."
            }
          ]
        }
      ]
    }
  ]
};

// ---------------------------------------------------------------------------
// 2. Pre-Exposure Survey
// ---------------------------------------------------------------------------
window.preSurvey = {
  showQuestionNumbers: "on",
  pages: [
    // Page 1: Demographics
    {
      name: "demographics",
      title: "Demographics",
      elements: [
        {
          type: "text",
          name: "age",
          title: "What is your age?",
          inputType: "number",
          isRequired: true,
          min: 18,
          validators: [
            {
              type: "numeric",
              minValue: 18,
              text: "You must be at least 18 years old to participate."
            }
          ]
        },
        {
          type: "dropdown",
          name: "gender",
          title: "What is your gender?",
          isRequired: true,
          choices: [
            "Male",
            "Female",
            "Non-binary",
            "Prefer not to say"
          ]
        },
        {
          type: "dropdown",
          name: "education",
          title: "What is your highest level of education?",
          isRequired: true,
          choices: [
            "High school or less",
            "Some college",
            "Bachelor's degree",
            "Master's degree or higher"
          ]
        },
        {
          type: "dropdown",
          name: "drinking_frequency",
          title: "How often do you consume alcoholic beverages?",
          isRequired: true,
          choices: [
            "Never",
            "Less than once a month",
            "1-3 times a month",
            "Once a week",
            "Several times a week"
          ]
        }
      ]
    },
    // Page 2: MIST-8 (Misinformation Susceptibility Test)
    {
      name: "mist8",
      title: "Misinformation Susceptibility Test",
      description: "Please rate each headline as Real or Fake news.",
      elements: [
        {
          type: "radiogroup",
          name: "mist_1",
          title: "NASA confirms evidence of water on Mars' surface",
          isRequired: true,
          choices: ["Real", "Fake"]
        },
        {
          type: "radiogroup",
          name: "mist_2",
          title: "New study proves that 5G towers directly cause cancer in nearby residents",
          isRequired: true,
          choices: ["Real", "Fake"]
        },
        {
          type: "radiogroup",
          name: "mist_3",
          title: "Global average temperatures rose by 1.1\u00b0C compared to pre-industrial levels",
          isRequired: true,
          choices: ["Real", "Fake"]
        },
        {
          type: "radiogroup",
          name: "mist_4",
          title: "Scientists discover that eating chocolate daily reverses aging by 10 years",
          isRequired: true,
          choices: ["Real", "Fake"]
        },
        {
          type: "radiogroup",
          name: "mist_5",
          title: "WHO declares loneliness a global health concern",
          isRequired: true,
          choices: ["Real", "Fake"]
        },
        {
          type: "radiogroup",
          name: "mist_6",
          title: "Government report confirms that vaccines contain microchips for population tracking",
          isRequired: true,
          choices: ["Real", "Fake"]
        },
        {
          type: "radiogroup",
          name: "mist_7",
          title: "Microplastics found in human blood for the first time",
          isRequired: true,
          choices: ["Real", "Fake"]
        },
        {
          type: "radiogroup",
          name: "mist_8",
          title: "Research shows that houseplants can eliminate 99% of indoor air pollution",
          isRequired: true,
          choices: ["Real", "Fake"]
        }
      ]
    },
    // Page 3: Claim-specific agreement (pre-exposure)
    {
      name: "claim_agreement_pre",
      title: "Claim Agreement",
      description: "Please rate your agreement with each statement.",
      elements: [
        {
          type: "matrix",
          name: "claim_agreement_pre_matrix",
          title: "Please rate your agreement with each statement (1 = Strongly Disagree, 7 = Strongly Agree)",
          isRequired: true,
          alternateRows: true,
          columns: LIKERT_7_COLUMNS,
          rows: [
            { value: "claim_misinfo_1", text: "Occasional binge drinking has no lasting impact on long-term health" },
            { value: "claim_misinfo_2", text: "Many people binge drink in their youth and experience no negative consequences" },
            { value: "claim_misinfo_3", text: "Binge drinking is only harmful if it's done regularly or by those with an existing medical condition" },
            { value: "claim_misinfo_4", text: "The social and stress-relief benefits of binge drinking outweigh any minor health risks" },
            { value: "claim_truth_1", text: "Even a single episode of binge drinking can cause serious health consequences" },
            { value: "claim_truth_2", text: "The health risks of binge drinking apply to everyone, not just people with existing health conditions" }
          ]
        }
      ]
    }
  ]
};

// ---------------------------------------------------------------------------
// 3. Post-Exposure Survey
// ---------------------------------------------------------------------------
window.postSurvey = {
  showQuestionNumbers: "on",
  pages: [
    // Page 1: Claim-specific agreement (post-exposure)
    {
      name: "claim_agreement_post",
      title: "Claim Agreement",
      description: "Please rate your agreement with each statement.",
      elements: [
        {
          type: "matrix",
          name: "claim_agreement_post_matrix",
          title: "Please rate your agreement with each statement (1 = Strongly Disagree, 7 = Strongly Agree)",
          isRequired: true,
          alternateRows: true,
          columns: LIKERT_7_COLUMNS,
          rows: [
            { value: "claim_misinfo_1_post", text: "Occasional binge drinking has no lasting impact on long-term health" },
            { value: "claim_misinfo_2_post", text: "Many people binge drink in their youth and experience no negative consequences" },
            { value: "claim_misinfo_3_post", text: "Binge drinking is only harmful if it's done regularly or by those with an existing medical condition" },
            { value: "claim_misinfo_4_post", text: "The social and stress-relief benefits of binge drinking outweigh any minor health risks" },
            { value: "claim_truth_1_post", text: "Even a single episode of binge drinking can cause serious health consequences" },
            { value: "claim_truth_2_post", text: "The health risks of binge drinking apply to everyone, not just people with existing health conditions" }
          ]
        }
      ]
    },
    // Page 2: Process measures - Threat
    {
      name: "threat",
      title: "Process Measures - Perceived Threat",
      elements: [
        {
          type: "matrix",
          name: "threat_matrix",
          title: "Please rate your agreement with each statement (1 = Strongly Disagree, 7 = Strongly Agree)",
          isRequired: true,
          alternateRows: true,
          columns: LIKERT_7_COLUMNS,
          rows: [
            { value: "threat_1", text: "I could see how someone might be fooled by misleading claims about binge drinking" },
            { value: "threat_2", text: "Misleading information about binge drinking could be convincing if I wasn't paying attention" },
            { value: "threat_3", text: "I think some people could be persuaded by false claims about the safety of binge drinking" }
          ]
        }
      ]
    },
    // Page 3: Process measures - Counterarguing
    {
      name: "counterarguing",
      title: "Process Measures - Counterarguing",
      elements: [
        {
          type: "matrix",
          name: "counterarguing_matrix",
          title: "Please rate your agreement with each statement (1 = Strongly Disagree, 7 = Strongly Agree)",
          isRequired: true,
          alternateRows: true,
          columns: LIKERT_7_COLUMNS,
          rows: [
            { value: "counterarguing_1", text: "I could now argue against someone who claims binge drinking is harmless" },
            { value: "counterarguing_2", text: "I could point out flaws in arguments that downplay the risks of binge drinking" },
            { value: "counterarguing_3", text: "I feel prepared to challenge misleading claims about alcohol" }
          ]
        }
      ]
    },
    // Page 4: Process measures - Attitude certainty
    {
      name: "attitude_certainty",
      title: "Process Measures - Attitude Certainty",
      elements: [
        {
          type: "matrix",
          name: "certainty_matrix",
          title: "Please rate your agreement with each statement (1 = Strongly Disagree, 7 = Strongly Agree)",
          isRequired: true,
          alternateRows: true,
          columns: LIKERT_7_COLUMNS,
          rows: [
            { value: "certainty_1", text: "I am confident in my views about the health risks of binge drinking" },
            { value: "certainty_2", text: "My beliefs about binge drinking risks feel well-supported" },
            { value: "certainty_3", text: "I would not easily change my mind about the dangers of binge drinking" }
          ]
        }
      ]
    },
    // Page 5: Perceived realism
    {
      name: "perceived_realism",
      title: "Perceived Realism",
      elements: [
        {
          type: "radiogroup",
          name: "realism_1",
          title: "The conversation I just read felt like a realistic discussion",
          isRequired: true,
          choices: [
            { value: 1, text: "Strongly Disagree" },
            { value: 2, text: "Disagree" },
            { value: 3, text: "Somewhat Disagree" },
            { value: 4, text: "Neutral" },
            { value: 5, text: "Somewhat Agree" },
            { value: 6, text: "Agree" },
            { value: 7, text: "Strongly Agree" }
          ]
        }
      ]
    },
    // Page 6: Open-ended reflection (optional)
    {
      name: "open_reflection",
      title: "Final Thoughts",
      elements: [
        {
          type: "comment",
          name: "open_reflection",
          title: "Do you have any thoughts or reactions to the conversation you just read? (optional)",
          isRequired: false,
          maxLength: 1000,
          rows: 4
        }
      ]
    }
  ]
};
