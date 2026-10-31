*** Settings ***
Documentation    Accueil et liste des formations du portail ; aucune donnée de recette implicite.
Resource    ../browser.resource

*** Variables ***
${MY_TRAININGS_LINK}    a[href="/my/trainings"]

*** Keywords ***
Ouvrir la liste depuis l'accueil du portail
    Go To    ${BASE_URL}/my/home
    Click    ${MY_TRAININGS_LINK}
    Wait For Elements State    h1    visible

Ouvrir une inscription depuis la liste
    [Arguments]    ${enrollment_id}
    Click    a[href="/my/trainings/${enrollment_id}"]
    Wait For Elements State    h1    visible

Compter les liens vers une inscription
    [Arguments]    ${enrollment_id}
    ${count}=    Get Element Count    a[href="/my/trainings/${enrollment_id}"]
    RETURN    ${count}
