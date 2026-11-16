// Match the former browser compiler configuration, using the pinned local CLI.
module.exports = {
  content: ['./templates/**/*.html', './static/js/*.js'],
  corePlugins: {preflight: false},
  theme: {extend: {
    colors: {canvas:'#e8e5df', cream:'#f4f2ec', charcoal:'#2a2826', ink:'#1c1a18', muted:'#6b665f'},
    fontFamily: {sans:['Arial','Helvetica','sans-serif']},
  }},
};
