*** Settings ***
Documentation    Détail d'une formation : supports privés, formulaire de dépôt et échanges.
Resource    ../browser.resource

*** Variables ***
${TRAINING_TITLE}    h1
${SUBMISSION_ERROR}    .alert-danger
${LEARNING_ENTRIES}    [id^="learning-entry-"]
${ENTRY_BODY}    ${LEARNING_ENTRIES} .text-break

*** Keywords ***
Lire le titre de la formation
    ${title}=    Get Text    ${TRAINING_TITLE}
    RETURN    ${title}

Télécharger un support privé
    [Arguments]    ${material_id}    ${destination}
    ${pending}=    Promise To Wait For Download    saveAs=${destination}
    Click    a[href*="/web/content/training.material/${material_id}/data"]
    ${download}=    Wait For    ${pending}
    RETURN    ${download}[saveAs]

Charger une inscription par son lien direct
    [Arguments]    ${enrollment_id}
    ${response}=    Naviguer vers une ressource privée    /my/trainings/${enrollment_id}
    RETURN    ${response}

Charger un support par son lien direct
    [Arguments]    ${material_id}
    ${response}=    Naviguer vers une ressource privée
    ...    /web/content/training.material/${material_id}/data?filename_field=filename&download=true
    RETURN    ${response}

Naviguer vers une ressource privée
    [Arguments]    ${path}
    [Tags]    robot:private
    ${pending}=    Promise To    Wait For Response    ${BASE_URL}${path}
    Go To    ${BASE_URL}${path}
    ${response}=    Wait For    ${pending}
    RETURN    ${response}

Saisir le texte du dépôt
    [Arguments]    ${activity_id}    ${text}
    Fill Text    id=work-${activity_id}    ${text}

Joindre le fichier du dépôt
    [Arguments]    ${activity_id}    ${file}
    Upload File By Selector    id=file-${activity_id}    ${file}

Envoyer le formulaire de dépôt
    [Arguments]    ${activity_id}
    Click    css=#learning-activity-${activity_id} button[type="submit"]

Attendre le refus du dépôt
    Wait For Elements State    ${SUBMISSION_ERROR}    visible

Lire le brouillon du dépôt
    [Arguments]    ${activity_id}
    ${draft}=    Get Property    id=work-${activity_id}    value
    RETURN    ${draft}

Compter les dépôts affichés
    ${count}=    Get Element Count    ${LEARNING_ENTRIES}
    RETURN    ${count}

Attendre un dépôt enregistré
    Wait For Elements State    ${SUBMISSION_ERROR}    detached
    Wait For Elements State    ${LEARNING_ENTRIES}    visible

Lire le texte du dépôt enregistré
    ${text}=    Get Text    ${ENTRY_BODY}
    RETURN    ${text}

Lire les noms des fichiers déposés
    ${names}=    Get Text    ${LEARNING_ENTRIES}
    RETURN    ${names}

Recharger la formation
    Reload
    Wait For Elements State    ${TRAINING_TITLE}    visible
