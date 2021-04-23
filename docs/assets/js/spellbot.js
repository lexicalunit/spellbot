var SpellBotJS = {
  init : function() {
    const link = $('#main-navbar .navbar-nav .nav-item:last-child .nav-link')
    link.href = 'https://top.gg/bot/725510263251402832';
    link.html('<img src="https://top.gg/api/widget/status/725510263251402832.svg?noavatar=true" alt="" width="123" height="20" />')
  },
};

document.addEventListener('DOMContentLoaded', SpellBotJS.init);
