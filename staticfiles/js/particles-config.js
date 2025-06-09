// Particles.js configuration
const particlesConfig = {
    particles: {
        number: {
            value: 100,
            density: {
                enable: true,
                value_area: 800
            }
        },
        color: {
            value: ['#4f46e5', '#3b82f6', '#60a5fa']
        },
        shape: {
            type: ['circle', 'triangle'],
            stroke: {
                width: 0,
                color: '#e5e7eb'
            },
            polygon: {
                nb_sides: 5
            }
        },
        opacity: {
            value: 0.3,
            random: true,
            anim: {
                enable: true,
                speed: 1.5,
                opacity_min: 0.1,
                sync: false
            }
        },
        size: {
            value: 3,
            random: true,
            anim: {
                enable: true,
                speed: 3,
                size_min: 0.1,
                sync: false
            }
        },
        line_linked: {
            enable: true,
            distance: 150,
            color: '#4f46e5',
            opacity: 0.2,
            width: 1
        },
        move: {
            enable: true,
            speed: 3,
            direction: 'none',
            random: true,
            straight: false,
            out_mode: 'out',
            bounce: false,
            attract: {
                enable: true,
                rotateX: 600,
                rotateY: 1200
            }
        }
    },
    interactivity: {
        detect_on: 'canvas',
        events: {
            onhover: {
                enable: true,
                mode: 'grab'
            },
            onclick: {
                enable: true,
                mode: 'push'
            },
            resize: true
        },
        modes: {
            grab: {
                distance: 180,
                line_linked: {
                    opacity: 0.4
                }
            },
            push: {
                particles_nb: 6
            }
        }
    },
    retina_detect: true
};

// Initialize particles
function initParticles() {
    if (typeof particlesJS !== 'undefined') {
        particlesJS('particles-js', particlesConfig);
    }
}

// Initialize when document is ready
$(document).ready(function() {
    initParticles();
}); 