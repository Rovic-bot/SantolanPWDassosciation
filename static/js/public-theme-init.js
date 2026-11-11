/* Apply the saved public theme before the first paint. */
(() => {
    try {
        const saved = JSON.parse(localStorage.getItem('santolan-display') || '{}');
        document.documentElement.dataset.publicTheme = saved.dark === true ? 'dark' : 'light';
        document.documentElement.dataset.motion = saved.motion === true ? 'reduce' : 'system';
    } catch (_) { /* The display controls also work without storage. */ }
})();
