/**
 * Public course page: the comparison of formats follows the tab chosen in the
 * booking card, and its buttons open that tab without reloading the page.
 * Without JavaScript, the buttons reload the page on the chosen format.
 */
const SELECTED = "o_training_course_selected";
const PREFIX = "#training_booking_";

function selectFormat(key) {
    for (const cell of document.querySelectorAll(
        ".o_training_course_comparison th[data-format], .o_training_course_comparison td[data-format]"
    )) {
        cell.classList.toggle(SELECTED, cell.dataset.format === key);
    }
}

function formatOfTab(tab) {
    const target = tab && tab.dataset.bsTarget;
    return target && target.startsWith(PREFIX) ? target.slice(PREFIX.length) : null;
}

document.addEventListener("shown.bs.tab", (ev) => {
    const key = formatOfTab(ev.target.closest && ev.target.closest(".o_training_course_tabs [role='tab']"));
    if (key) {
        selectFormat(key);
    }
});

document.addEventListener("click", (ev) => {
    if (!ev.target.closest) {
        return;
    }
    const tab = ev.target.closest(".o_training_course_tabs [role='tab']");
    if (tab) {
        selectFormat(formatOfTab(tab));
        return;
    }
    const choice = ev.target.closest(".o_training_course_choose");
    const target = choice && document.getElementById(`training_booking_${choice.dataset.format}_tab`);
    if (!target) {
        return;
    }
    ev.preventDefault();
    target.click();
    selectFormat(choice.dataset.format);
    const booking = document.getElementById("training_course_booking");
    if (booking) {
        booking.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    target.focus({ preventScroll: true });
});
