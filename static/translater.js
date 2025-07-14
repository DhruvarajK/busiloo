const translations = {
    en: {
        "s01": "FROM",
        "s02": "Starting location",
        "s03": "TO",
        "s04": "Destination",
        "s05": "DATE OF JOURNEY",
        "s06": "Search Buses",
        "s07": "Search by Bus Name",
        "s08": "Find a specific bus service",
        "s09": "Stops Near Me",
        "s10": "Find bus stops and routes around you",
        "s11": "Calculate fare",
        "s12": "Estimate your travel cost.",
        "s13": "Feedback",
        "s14": "Share your experience with us.",
        "s15": "Report Traffic",
        "s16": "Notify us about traffic issues."
    },

    ml: {
        "s01": "നിന്ന്",
        "s02": "പുറപ്പെടുന്ന സ്ഥലം",
        "s03": "ലേക്ക്",
        "s04": "എത്തിച്ചേരേണ്ട സ്ഥലം",
        "s05": "യാത്രാ തീയതി",
        "s06": "ബസുകൾ തിരയുക",
        "s07": "ബസ് പേര് ഉപയോഗിച്ച് തിരയുക",
        "s08": "ഒരു പ്രത്യേക ബസ് സർവീസ് കണ്ടെത്തുക",
        "s09": "എന്റെ അടുത്തുള്ള സ്റ്റോപ്പുകൾ",
        "s10": "നിങ്ങളുടെ അടുത്തുള്ള ബസ് സ്റ്റോപ്പുകളും റൂട്ടുകളും കണ്ടെത്തുക",
        "s11": "യാത്രാക്കൂലി കണക്കാക്കുക",
        "s12": "നിങ്ങളുടെ യാത്രാ ചിലവ് കണക്കാക്കുക.",
        "s13": "അഭിപ്രായം",
        "s14": "നിങ്ങളുടെ അനുഭവം ഞങ്ങളുമായി പങ്കിടുക.",
        "s15": "ട്രാഫിക് റിപ്പോർട്ട് ചെയ്യുക",
        "s16": "ട്രാഫിക് പ്രശ്നങ്ങളെക്കുറിച്ച് ഞങ്ങളെ അറിയിക്കുക."
    }
};

// Function to set the language and update content
function setLanguage(lang) {
    // Store the selected language in localStorage
    localStorage.setItem('selectedLanguage', lang);

    // Update the 'lang' attribute of the HTML tag
    document.documentElement.lang = lang;

    // Set the dropdown's selected value
    const langSelect = document.getElementById('language-select');
    if (langSelect) {
        langSelect.value = lang;
    }

    // Iterate over all elements with a 'data-translate' attribute (for textContent)
    document.querySelectorAll('[data-translate]').forEach(element => {
        const key = element.getAttribute('data-translate');
        if (translations[lang] && translations[lang][key]) {
            element.textContent = translations[lang][key];
        }
    });

    // Iterate over all elements with a 'data-translate-placeholder' attribute (for placeholder)
    document.querySelectorAll('[data-translate-placeholder]').forEach(element => {
        const key = element.getAttribute('data-translate-placeholder');
        if (translations[lang] && translations[lang][key]) {
            element.placeholder = translations[lang][key];
        }
    });

    document.querySelectorAll('[data-translate-button]').forEach(element => {
        const key = element.getAttribute('data-translate-button');
        if (translations[lang] && translations[lang][key]) {
            element.textContent = translations[lang][key];
        }
    });
}

// Get the language select dropdown
const languageSelect = document.getElementById('language-select');

// Add an 'change' event listener to the dropdown
if (languageSelect) {
    languageSelect.addEventListener('change', (event) => {
        const selectedLang = event.target.value;
        setLanguage(selectedLang);
    });
}


// Initialize the page with the stored language or default to English
document.addEventListener('DOMContentLoaded', () => {
    const storedLang = localStorage.getItem('selectedLanguage') || 'en';
    setLanguage(storedLang); // Call setLanguage to apply translations and set dropdown value
});