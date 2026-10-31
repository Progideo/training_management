*** Settings ***
Documentation    Bibliothèque métier : compose les pages et porte les assertions fonctionnelles.
Resource    ../pages/login_page.resource
Resource    ../pages/portal_page.resource
Resource    ../pages/training_page.resource
Resource    ../pages/category_page.resource
Library    OperatingSystem
Library    String

*** Keywords ***
Se connecter comme
    [Arguments]    ${role}
    [Documentation]    Authentifie un compte de recette au rôle restreint configurable.
    ${login}=    Get Environment Variable    TM_BROWSER_${role}    browser_${role.lower()}
    login_page.Ouvrir la page de connexion
    login_page.Saisir les identifiants et se connecter    ${login}

Consulter ma formation
    [Arguments]    ${enrollment_id}    ${expected_name}
    [Documentation]    Rejoint l'inscription par les liens du portail et vérifie son identité.
    portal_page.Ouvrir la liste depuis l'accueil du portail
    portal_page.Ouvrir une inscription depuis la liste    ${enrollment_id}
    ${title}=    training_page.Lire le titre de la formation
    Should Be Equal    ${title}    ${expected_name}

Vérifier le contenu de mon support privé
    [Arguments]    ${material_id}    ${expected_content}
    [Documentation]    Télécharge par le lien affiché puis compare les octets attendus.
    ${file}=    training_page.Télécharger un support privé    ${material_id}    ${OUTPUTDIR}/fictional-browser.pdf
    File Should Exist    ${file}
    ${actual}=    Get Binary File    ${file}
    ${expected}=    Encode String To Bytes    ${expected_content}    UTF-8
    Should Be Equal    ${actual}    ${expected}

Vérifier que la formation d'un tiers est inaccessible
    [Arguments]    ${enrollment_id}    ${material_id}
    [Documentation]    Contrôle le lien absent et les refus serveur via deux navigations réelles.
    portal_page.Ouvrir la liste depuis l'accueil du portail
    ${count}=    portal_page.Compter les liens vers une inscription    ${enrollment_id}
    Should Be Equal As Integers    ${count}    0
    ${enrollment}=    training_page.Charger une inscription par son lien direct    ${enrollment_id}
    Should Be Equal As Integers    ${enrollment}[status]    404
    ${material}=    training_page.Charger un support par son lien direct    ${material_id}
    Should Be Equal As Integers    ${material}[status]    404
    Should Not Contain    ${material}[body]    %PDF-1.4

Déposer un travail pédagogique
    [Arguments]    ${activity_id}    ${text}    ${file}
    [Documentation]    Saisit le texte, joint le fichier et soumet le formulaire utilisateur.
    training_page.Saisir le texte du dépôt    ${activity_id}    ${text}
    training_page.Joindre le fichier du dépôt    ${activity_id}    ${file}
    training_page.Envoyer le formulaire de dépôt    ${activity_id}

Vérifier le refus sans perte du brouillon
    [Arguments]    ${activity_id}    ${expected_text}
    [Documentation]    Exige une erreur visible, le texte conservé et aucun dépôt enregistré.
    training_page.Attendre le refus du dépôt
    ${draft}=    training_page.Lire le brouillon du dépôt    ${activity_id}
    Should Be Equal    ${draft}    ${expected_text}
    ${count}=    training_page.Compter les dépôts affichés
    Should Be Equal As Integers    ${count}    0

Corriger uniquement le fichier du dépôt
    [Arguments]    ${activity_id}    ${file}
    [Documentation]    Resoumet sans ressaisir le texte, pour vérifier la conservation du brouillon.
    training_page.Joindre le fichier du dépôt    ${activity_id}    ${file}
    training_page.Envoyer le formulaire de dépôt    ${activity_id}

Vérifier la conservation du travail enregistré
    [Arguments]    ${expected_text}    ${expected_filename}
    [Documentation]    Vérifie un unique dépôt, puis sa persistance et son fichier après rechargement.
    training_page.Attendre un dépôt enregistré
    ${count}=    training_page.Compter les dépôts affichés
    Should Be Equal As Integers    ${count}    1
    ${text}=    training_page.Lire le texte du dépôt enregistré
    Should Be Equal    ${text}    ${expected_text}
    training_page.Recharger la formation
    ${text}=    training_page.Lire le texte du dépôt enregistré
    Should Be Equal    ${text}    ${expected_text}
    ${files}=    training_page.Lire les noms des fichiers déposés
    Should Contain    ${files}    ${expected_filename}

Créer une catégorie de formation
    [Arguments]    ${action_id}    ${name}
    [Documentation]    Utilise uniquement la liste et le formulaire natifs avec le compte connecté.
    category_page.Ouvrir la liste des catégories    ${action_id}
    category_page.Créer une catégorie dans le formulaire    ${name}

Vérifier la conservation de la catégorie
    [Arguments]    ${expected_name}
    [Documentation]    Relit le nom depuis le serveur après rechargement du formulaire.
    category_page.Recharger la catégorie
    ${name}=    category_page.Lire le nom de la catégorie
    Should Be Equal    ${name}    ${expected_name}
