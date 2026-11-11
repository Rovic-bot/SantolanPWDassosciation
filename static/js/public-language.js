/* Local display translations. Original text, form values and published records stay intact. */
WorkspacePage.run(({on, cleanup}) => {
    if (!document.body.classList.contains('public-portal') || document.querySelector('[data-portal-page]')) return;
    const normalize = value => value.replace(/\s+/g, ' ').replace(/[’‘]/g, "'").replace(/[–—]/g, '-').trim();
    const catalog = new Map(Object.entries(window.PublicTagalog || {}).map(([en, tl]) => [normalize(en).toLowerCase(), tl]));
    const texts = new WeakMap(), attributes = new WeakMap();
    const excluded = 'script,style,template,svg,textarea,input,[contenteditable],[translate="no"],[data-no-translate],[data-public-language],.portal-saved-copy';
    let active = false, queued = false, lastLanguage;
    const translate = value => {
        const key = normalize(value);
        const exact = catalog.get(key.toLowerCase());
        if (exact) return exact;
        let match;
        if ((match = key.match(/^([←→↗])\s*(.+)$/))) return `${match[1]} ${translate(match[2])}`;
        if ((match = key.match(/^(\d+) of (\d+)(?:: (.+))?$/))) return `${match[1]} sa ${match[2]}${match[3] ? ': ' + translate(match[3]) : ''}`;
        if ((match = key.match(/^(.+)\. Card (\d+) of (\d+)\.$/))) return `${translate(match[1])}. Kard ${match[2]} sa ${match[3]}.`;
        if ((match = key.match(/^Show (.+) \((\d+) of (\d+)\)$/))) return `Ipakita ang ${translate(match[1])} (${match[2]} sa ${match[3]})`;
        if ((match = key.match(/^Cards? (\d+)(?: to (\d+))? of (\d+)$/))) return `Mga kard ${match[1]}${match[2] ? ' hanggang ' + match[2] : ''} sa ${match[3]}`;
        if ((match = key.match(/^Showing (\d+)-(\d+) of (\d+) programs$/i))) return `Ipinapakita ang ${match[1]}-${match[2]} sa ${match[3]} programa`;
        if ((match = key.match(/^(Page|Read|View|for|Results:|View event:) (.+)$/i))) return `${({page:'Pahina',read:'Basahin',view:'Tingnan',for:'para sa','results:':'Mga resulta:','view event:':'Tingnan ang kaganapan:'})[match[1].toLowerCase()]} ${match[2]}`;
        if ((match = key.match(/^(\d+) published (programs|events)$/))) return `${match[1]} nailathalang ${match[2] === 'programs' ? 'programa' : 'kaganapan'}`;
        if ((match = key.match(/^(\d+) active Association members\. Read the membership guide\.$/))) return `${match[1]} aktibong kasapi ng Samahan. Basahin ang gabay sa pagiging kasapi.`;
        if ((match = key.match(/^(\d+) notices$/))) return `${match[1]} anunsiyo`;
        if ((match = key.match(/^© (\d+) Barangay Santolan PWD Association\. All rights reserved\.$/))) return `© ${match[1]} Barangay Santolan PWD Association. Nakalaan ang lahat ng karapatan.`;
        if ((match = key.match(/^(.+) - no program image$/))) return `${translate(match[1])} - walang larawan ng programa`;
        // Dates retain their original numerical values and time zone.
        const months = {January:'Enero',February:'Pebrero',March:'Marso',April:'Abril',May:'Mayo',June:'Hunyo',July:'Hulyo',August:'Agosto',September:'Setyembre',October:'Oktubre',November:'Nobyembre',December:'Disyembre',Jan:'Ene',Feb:'Peb',Mar:'Mar',Apr:'Abr',Jun:'Hun',Jul:'Hul',Aug:'Ago',Sep:'Set',Oct:'Okt',Nov:'Nob',Dec:'Dis',Sunday:'Linggo',Monday:'Lunes',Tuesday:'Martes',Wednesday:'Miyerkules',Thursday:'Huwebes',Friday:'Biyernes',Saturday:'Sabado'};
        if (/\d|Every year/.test(key) && /^(Published )?(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\b/.test(key)) {
            return key.replace(/^Published /,'Inilathala noong ').replace(/\b[A-Z][a-z]+\b/g, word => months[word] || word).replace('Every year','Taun-taon');
        }
        return value;
    };
    function replace(original) {
        if (!active || !original.trim()) return original;
        const translated = translate(original.trim());
        return original.match(/^\s*/)[0] + translated + original.match(/\s*$/)[0];
    }
    function apply() {
        queued = false;
        observer.disconnect();
        active = document.documentElement.dataset.language === 'tl';
        const languageChanged = active !== lastLanguage;
        lastLanguage = active;
        const lang = active ? 'fil' : 'en';
        if (document.documentElement.lang !== lang) document.documentElement.lang = lang;
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            const node = walker.currentNode;
            if (node.parentElement.closest(excluded)) continue;
            const state = texts.get(node);
            const source = state && node.data === state.output ? state.source : node.data;
            const output = replace(source);
            if (node.data !== output) node.data = output;
            texts.set(node, {source, output});
        }
        document.querySelectorAll('[aria-label],[placeholder],[title],[alt]').forEach(element => {
            if (element.closest('script,style,template,[contenteditable],[translate="no"],[data-no-translate],.portal-saved-copy')) return;
            const saved = attributes.get(element) || {};
            for (const name of ['aria-label','placeholder','title','alt']) {
                const value = element.getAttribute(name);
                if (value === null) continue;
                const state = saved[name];
                const source = state && value === state.output ? state.source : value;
                const output = replace(source);
                if (value !== output) element.setAttribute(name, output);
                saved[name] = {source, output};
            }
            attributes.set(element, saved);
        });
        const button = document.querySelector('[data-public-language]');
        if (button) { button.textContent = active ? 'English' : 'Tagalog'; button.setAttribute('aria-label', active ? 'Bumalik sa English' : 'Translate to Tagalog'); }
        observer.observe(document.body, {subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['aria-label','placeholder','title','alt']});
        if (languageChanged) document.dispatchEvent(new Event('santolan:languagechange'));
    }
    const observer = new MutationObserver(() => {
        if (!queued) { queued = true; queueMicrotask(apply); }
    });
    on(document, 'santolan:displaychange', apply);
    cleanup(() => observer.disconnect());
    apply();
});
