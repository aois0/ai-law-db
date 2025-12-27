
// 条文検索
document.getElementById('search')?.addEventListener('input', function(e) {
  const query = e.target.value.toLowerCase();
  const articles = document.querySelectorAll('.toc-article');

  articles.forEach(article => {
    const text = article.textContent.toLowerCase();
    article.style.display = text.includes(query) ? '' : 'none';
  });
});

// 目次の折りたたみ
document.querySelectorAll('.toc-heading').forEach(heading => {
  heading.addEventListener('click', function() {
    const children = this.nextElementSibling;
    if (children && children.classList.contains('toc-children')) {
      children.style.display = children.style.display === 'none' ? '' : 'none';
    }
  });
});

// 現在の条文をビューに表示
document.querySelector('.toc-article.current')?.scrollIntoView({
  behavior: 'smooth',
  block: 'center'
});
