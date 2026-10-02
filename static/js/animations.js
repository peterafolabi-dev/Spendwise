// Global Animation Utilities

function isReducedMotion() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// 1. Number Count Up
function animateNumberCountUp(el) {
    if (isReducedMotion()) return;
    
    const targetText = el.innerText.replace(/[^0-9.]/g, '');
    const targetVal = parseFloat(targetText);
    if (isNaN(targetVal)) return;
    
    const prefix = el.innerText.startsWith('$') ? '$' : '';
    const duration = 700; // ms
    const startTime = performance.now();
    
    function updateNumber(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // ease-out cubic
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        const currentVal = targetVal * easeProgress;
        
        el.innerText = prefix + currentVal.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        
        if (progress < 1) {
            requestAnimationFrame(updateNumber);
        } else {
            el.innerText = prefix + targetVal.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }
    }
    
    requestAnimationFrame(updateNumber);
}

// 2. Staggered List Observer
function initStaggeredLists() {
    if (isReducedMotion()) return;
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const container = entry.target;
                const items = container.querySelectorAll('.animate-stagger-item:not(.is-visible)');
                
                items.forEach((item, index) => {
                    // Cap delay to 400ms max (40ms * 10 items)
                    const delay = Math.min(index * 40, 400);
                    setTimeout(() => {
                        item.classList.add('is-visible');
                    }, delay);
                });
                observer.unobserve(container);
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.stagger-container').forEach(container => {
        observer.observe(container);
    });
}

// 3. Progress Bars
function initProgressBars() {
    if (isReducedMotion()) {
        document.querySelectorAll('.progress-fill').forEach(bar => {
            bar.style.transform = `scaleX(${bar.getAttribute('data-progress') || 1})`;
        });
        return;
    }
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const bar = entry.target;
                const progress = bar.getAttribute('data-progress') || 0;
                bar.style.setProperty('--progress-width', progress);
                bar.classList.add('filled');
                observer.unobserve(bar);
            }
        });
    });
    
    document.querySelectorAll('.progress-fill').forEach(bar => observer.observe(bar));
}

// Initialize everything on DOM Content Loaded
document.addEventListener('DOMContentLoaded', () => {
    // Wrap main content in fade-in-up
    const main = document.querySelector('main');
    if (main && !isReducedMotion()) {
        main.classList.add('animate-fade-in-up');
    }

    // Enable smooth theme transitions AFTER initial load
    setTimeout(() => {
        document.body.classList.add('theme-transition');
    }, 100);

    // Apply number counter to currency elements
    document.querySelectorAll('.count-up').forEach(animateNumberCountUp);
    
    // Init staggered lists
    initStaggeredLists();
    
    // Init progress bars
    initProgressBars();
    
    // Chart draw animations
    if (!isReducedMotion()) {
        setTimeout(() => {
            document.querySelectorAll('.svg-grow-bar').forEach((bar, i) => {
                setTimeout(() => bar.classList.add('grown'), i * 50);
            });
            document.querySelectorAll('.svg-draw-line').forEach(line => line.classList.add('drawn'));
        }, 300);
    }
});
