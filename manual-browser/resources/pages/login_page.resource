*** Settings ***
Documentation    Page de connexion Odoo : sélecteurs, saisie et attente de navigation.
Resource    ../browser.resource

*** Variables ***
${LOGIN_INPUT}    input[name="login"]
${PASSWORD_INPUT}    input[name="password"]
${LOGIN_SUBMIT}    .oe_login_form button[type="submit"]

*** Keywords ***
Ouvrir la page de connexion
    Go To    ${BASE_URL}/web/login
    Wait For Elements State    ${LOGIN_INPUT}    visible

Saisir les identifiants et se connecter
    [Arguments]    ${login}
    [Documentation]    Le mot de passe est résolu par Fill Secret, sans retour ni journalisation.
    Fill Text    ${LOGIN_INPUT}    ${login}
    Fill Secret    ${PASSWORD_INPUT}    %TM_BROWSER_PASSWORD
    Click    ${LOGIN_SUBMIT}
    Wait For Elements State    ${PASSWORD_INPUT}    detached
