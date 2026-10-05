/**
 * SpendWise Contextual Typewriter Utility
 * Lightweight, accessible, CLS-safe typing animation
 */

(function(window) {
    'use strict';

    function initTypewriter(element, phrases, options) {
        if (!element || !Array.isArray(phrases) || phrases.length === 0) return null;

        options = options || {};
        const typingSpeed = options.typingSpeed || 45;
        const pauseTime = options.pauseTime || 2200;
        const backspacingSpeed = options.backspacingSpeed || 25;
        const loop = options.loop !== false;
        const onPhraseChange = options.onPhraseChange || null;

        // Accessibility: respect prefers-reduced-motion
        const isReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (isReducedMotion) {
            element.textContent = phrases[0];
            if (typeof onPhraseChange === 'function') {
                onPhraseChange(phrases[0]);
            }
            return {
                destroy: function() {}
            };
        }

        let phraseIndex = 0;
        let charIndex = 0;
        let isDeleting = false;
        let timeoutId = null;
        let isRunning = true;

        function tick() {
            if (!isRunning) return;

            const currentPhrase = phrases[phraseIndex];

            if (!isDeleting) {
                // Typing forwards
                charIndex++;
                element.textContent = currentPhrase.substring(0, charIndex);
                if (typeof onPhraseChange === 'function') {
                    onPhraseChange(currentPhrase.substring(0, charIndex));
                }

                if (charIndex === currentPhrase.length) {
                    if (!loop && phraseIndex === phrases.length - 1) {
                        return;
                    }
                    isDeleting = true;
                    timeoutId = setTimeout(tick, pauseTime);
                    return;
                }
                timeoutId = setTimeout(tick, typingSpeed);
            } else {
                // Backspacing
                charIndex--;
                element.textContent = currentPhrase.substring(0, charIndex);
                if (typeof onPhraseChange === 'function') {
                    onPhraseChange(currentPhrase.substring(0, charIndex));
                }

                if (charIndex === 0) {
                    isDeleting = false;
                    phraseIndex = (phraseIndex + 1) % phrases.length;
                    timeoutId = setTimeout(tick, 300);
                    return;
                }
                timeoutId = setTimeout(tick, backspacingSpeed);
            }
        }

        timeoutId = setTimeout(tick, options.initialDelay || 350);

        return {
            destroy: function() {
                isRunning = false;
                if (timeoutId) clearTimeout(timeoutId);
            }
        };
    }

    window.initTypewriter = initTypewriter;

})(window);

