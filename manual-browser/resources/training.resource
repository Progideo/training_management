*** Settings ***
Library    Browser    timeout=20s
Library    OperatingSystem

*** Keywords ***
Ouvrir une session isolée
    New Browser    chromium    headless=${HEADLESS}
    New Context    acceptDownloads=${True}    locale=en-US
    New Page    ${BASE_URL}/web/login

Se connecter comme
    [Arguments]    ${role}
    ${login}=    Get Environment Variable    TM_BROWSER_${role}    browser_${role.lower()}
    Fill Text    input[name="login"]    ${login}
    Fill Secret    input[name="password"]    %TM_BROWSER_PASSWORD
    Click    .oe_login_form button[type="submit"]
    Wait For Elements State    input[name="password"]    detached

Ouvrir mes formations
    Go To    ${BASE_URL}/my/home
    Click    a[href="/my/trainings"]
    Get Url    *=    /my/trainings

Ouvrir la formation de recette
    Ouvrir mes formations
    Click    a[href="/my/trainings/${ENROLLMENT}"]
    Wait For Elements State    h1    visible
    Get Text    h1    ==    Fictional browser training

Vérifier le refus de la ressource
    [Arguments]    ${path}
    ${pending}=    Promise To    Wait For Response    ${BASE_URL}${path}
    Go To    ${BASE_URL}${path}
    ${response}=    Wait For    ${pending}
    Should Be Equal As Integers    ${response}[status]    404
    Get Text    body    not contains    Fictional private browser PDF

Terminer le parcours
    Run Keyword If Test Failed    Take Screenshot
    Close Browser    ALL
