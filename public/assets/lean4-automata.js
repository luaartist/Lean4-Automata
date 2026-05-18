const tabButtons = document.querySelectorAll('[role="tab"]');

function activateTab(button) {
  const panelId = button.getAttribute('aria-controls');
  if (!panelId) return;

  tabButtons.forEach((item) => {
    const controlled = item.getAttribute('aria-controls');
    item.setAttribute('aria-selected', item === button ? 'true' : 'false');
    item.tabIndex = item === button ? 0 : -1;
    if (controlled) {
      const panel = document.getElementById(controlled);
      if (panel) panel.hidden = item !== button;
    }
  });
}

tabButtons.forEach((button) => {
  button.addEventListener('click', () => activateTab(button));
  button.addEventListener('keydown', (event) => {
    const buttons = Array.from(tabButtons);
    const index = buttons.indexOf(button);
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      const step = event.key === 'ArrowRight' ? 1 : -1;
      const next = buttons[(index + step + buttons.length) % buttons.length];
      next.focus();
      activateTab(next);
    }
  });
});