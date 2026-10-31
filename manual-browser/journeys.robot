*** Settings ***
Documentation    Parcours métier réels, manuels ; les détails de l'interface restent dans les pages.
Resource    resources/browser.resource
Resource    resources/business/training.resource
Test Setup    Ouvrir une session isolée
Test Teardown    Terminer le parcours

*** Variables ***
${TRAINING_NAME}    Fictional browser training
${PRIVATE_PDF_CONTENT}    %PDF-1.4\nFictional private browser PDF\n%%EOF
${DRAFT_TEXT}    Fictional draft <keep this text>
${CATEGORY_NAME}    Fictional category created in browser

*** Test Cases ***
Participant consulte sa formation et télécharge son support privé
    [Tags]    portal    private
    Se connecter comme    PARTICIPANT
    Consulter ma formation    ${ENROLLMENT}    ${TRAINING_NAME}
    Vérifier le contenu de mon support privé    ${MATERIAL}    ${PRIVATE_PDF_CONTENT}

Un tiers ne peut ouvrir ni inscription ni support privé
    [Tags]    isolation    private
    Se connecter comme    OUTSIDER
    Vérifier que la formation d'un tiers est inaccessible    ${ENROLLMENT}    ${MATERIAL}

Un dépôt refusé conserve le texte puis accepte la correction
    [Tags]    submission
    Se connecter comme    PARTICIPANT
    Consulter ma formation    ${ENROLLMENT}    ${TRAINING_NAME}
    Déposer un travail pédagogique    ${ACTIVITY}    ${DRAFT_TEXT}    ${OVERSIZE_FILE}
    Vérifier le refus sans perte du brouillon    ${ACTIVITY}    ${DRAFT_TEXT}
    Corriger uniquement le fichier du dépôt    ${ACTIVITY}    ${VALID_FILE}
    Vérifier la conservation du travail enregistré    ${DRAFT_TEXT}    fictional-work.pdf

Le coordinateur crée une catégorie par le formulaire natif
    [Tags]    internal
    Se connecter comme    COORDINATOR
    Créer une catégorie de formation    ${CATEGORY_ACTION}    ${CATEGORY_NAME}
    Vérifier la conservation de la catégorie    ${CATEGORY_NAME}
