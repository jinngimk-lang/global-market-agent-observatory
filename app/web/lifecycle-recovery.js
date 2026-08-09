(() => {
  let researchInterrupted = false;

  function researchControls() {
    return {
      primary: document.getElementById('research-button'),
      retry: document.getElementById('research-retry-button'),
      status: document.getElementById('research-status'),
    };
  }

  window.addEventListener('pagehide', () => {
    const {primary, retry} = researchControls();
    researchInterrupted = Boolean(
      primary?.disabled && retry?.disabled,
    );
  });

  window.addEventListener('pageshow', (event) => {
    if (!event.persisted || !researchInterrupted) return;

    const {primary, retry, status} = researchControls();
    if (!primary || !retry || !status) return;

    primary.disabled = false;
    primary.textContent = '拉取官方更新';
    retry.disabled = false;
    retry.hidden = false;
    status.textContent = '页面已恢复，先前研究请求已失效，可重试。';
    status.className = 'message negative';
    researchInterrupted = false;
  });
})();
