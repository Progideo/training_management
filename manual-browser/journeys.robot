*** Settings ***
Documentation    Parcours réels, à la demande uniquement. Données fictives et base jetable.
Resource    resources/training.resource
Test Setup    Ouvrir une session isolée
Test Teardown    Terminer le parcours

*** Variables ***
${BASE_URL}    %{TM_BASE_URL=http://127.0.0.1:18099}
${HEADLESS}    ${True}

*** Test Cases ***
Participant consulte sa formation et télécharge son support privé
    [Tags]    portal    private
    Se connecter comme    PARTICIPANT
    Ouvrir la formation de recette
    ${pending}=    Promise To Wait For Download    saveAs=${OUTPUTDIR}/fictional-browser.pdf
    Click    a[href*="/web/content/training.material/${MATERIAL}/data"]
    ${download}=    Wait For    ${pending}
    File Should Exist    ${OUTPUTDIR}/fictional-browser.pdf
    ${bytes}=    Get Binary File    ${OUTPUTDIR}/fictional-browser.pdf
    ${expected}=    Evaluate    b"%PDF-1.4\\nFictional private browser PDF\\n%%EOF"
    Should Be Equal    ${bytes}    ${expected}

Un tiers ne peut ouvrir ni inscription ni support privé
    [Tags]    isolation    private
    Se connecter comme    OUTSIDER
    Ouvrir mes formations
    Get Element Count    a[href="/my/trainings/${ENROLLMENT}"]    ==    0
    Vérifier le refus de la ressource    /my/trainings/${ENROLLMENT}
    Vérifier le refus de la ressource    /web/content/training.material/${MATERIAL}/data?filename_field=filename&download=true

Un dépôt refusé conserve le texte puis accepte la correction
    [Tags]    submission
    Se connecter comme    PARTICIPANT
    Ouvrir la formation de recette
    ${text}=    Set Variable    Fictional draft <keep this text>
    Fill Text    id=work-${ACTIVITY}    ${text}
    Upload File By Selector    id=file-${ACTIVITY}    ${OVERSIZE_FILE}
    Click    css=#learning-activity-${ACTIVITY} button[type="submit"]
    Wait For Elements State    .alert-danger    visible
    Get Property    id=work-${ACTIVITY}    value    ==    ${text}
    Get Element Count    [id^="learning-entry-"]    ==    0
    Upload File By Selector    id=file-${ACTIVITY}    ${VALID_FILE}
    Click    css=#learning-activity-${ACTIVITY} button[type="submit"]
    Wait For Elements State    .alert-danger    detached
    Wait For Elements State    [id^="learning-entry-"]    visible
    Get Element Count    [id^="learning-entry-"]    ==    1
    Get Text    [id^="learning-entry-"] .text-break    ==    ${text}
    Reload
    Get Text    [id^="learning-entry-"] .text-break    ==    ${text}
    Get Text    body    contains    fictional-work.pdf

Le coordinateur crée une catégorie par le formulaire natif
    [Tags]    internal
    Se connecter comme    COORDINATOR
    Go To    ${BASE_URL}/odoo/action-${CATEGORY_ACTION}
    Click    .o_list_button_add
    Fill Text    .o_field_widget[name="name"] input    Fictional category created in browser
    Click    .o_form_button_save
    Wait For Elements State    .o_form_button_save    hidden
    Reload
    Get Property    .o_field_widget[name="name"] input    value    ==    Fictional category created in browser
