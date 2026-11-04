(function ($) {
  'use strict';

  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) { $.fx.off = true; }

  /* ---------- Dữ liệu ---------- */
  var QUESTIONS = [
    { i: 'sun', q: 'Buổi sáng cuối tuần lý tưởng của bạn trông như thế nào?',
      o: ['Ngủ nướng, ở nhà một mình thật yên tĩnh', 'Rủ bạn bè đi cà phê, đi chơi từ sớm', 'Dọn góc làm việc, pha trà và đọc nốt cuốn sách dang dở', 'Đi dạo chậm trong công viên hoặc ngồi thiền'] },
    { i: 'mountain', q: 'Khi gặp khó khăn lớn, bạn thường làm gì?',
      o: ['Tự xoay xở, hiếm khi nhờ ai', 'Nhìn mặt tích cực và kể cho mọi người nghe', 'Lên kế hoạch kỹ rồi mới bắt tay vào làm', 'Bình tĩnh chờ đợi, tin rằng mọi chuyện sẽ qua'] },
    { i: 'palette', q: 'Bảng màu nào làm bạn thấy dễ chịu nhất?',
      o: ['Xanh rêu và xám đá', 'Vàng nắng và cam', 'Trắng và tím nhạt', 'Xanh ngọc và nâu gỗ'] },
    { i: 'desk', q: 'Bàn làm việc hoặc góc học của bạn thường ra sao?',
      o: ['Tối giản, chỉ có thứ cần dùng', 'Nhiều màu, nhiều ảnh, nhiều đồ lưu niệm', 'Gọn gàng, mọi thứ nằm đúng vị trí', 'Yên tĩnh, có cây xanh và ánh sáng dịu'] },
    { i: 'people', q: 'Trong nhóm bạn, bạn thường là người như thế nào?',
      o: ['Ít nói nhưng ai cũng tin tưởng', 'Người khuấy động không khí', 'Người để ý từng chi tiết nhỏ', 'Người lắng nghe và cho lời khuyên'] },
    { i: 'cup', q: 'Bạn chọn thức uống nào cho buổi chiều?',
      o: ['Cà phê đen không đường', 'Trà đào hoặc nước cam tươi', 'Trà hoa nhài hoặc hoa cúc', 'Trà xanh nóng, uống thật chậm'] },
    { i: 'alert', q: 'Điều nào làm bạn khó chịu nhất?',
      o: ['Phải phụ thuộc vào người khác', 'Một ngày buồn tẻ, chẳng có gì xảy ra', 'Làm việc dở dang, cẩu thả', 'Bị thúc ép, vội vàng, mất kiểm soát'] },
    { i: 'compass', q: 'Chuyến đi mơ ước của bạn là gì?',
      o: ['Một mình khám phá cao nguyên đá hoặc sa mạc', 'Lễ hội ngoài biển, đông bạn bè, đầy nắng', 'Thành phố cổ có bảo tàng và quán trà đẹp', 'Ngôi làng trên núi mờ sương, có ngôi chùa cổ'] },
    { i: 'drop', q: 'Nếu có một chậu cây, bạn sẽ chăm nó thế nào?',
      o: ['Quên tưới cả tuần cũng không sao', 'Tưới thật nhiều, nói chuyện với cây và chụp ảnh khoe', 'Lập lịch tưới chính xác, lau từng chiếc lá', 'Tỉa nhẹ mỗi ngày, kiên nhẫn chờ nhiều năm'] },
    { i: 'quote', q: 'Câu nói nào giống bạn nhất?',
      o: ['“Mạnh mẽ trong im lặng.”', '“Cứ hướng về phía mặt trời.”', '“Đẹp nằm ở từng chi tiết.”', '“Chậm mà chắc, càng lâu càng vững.”'] }
  ];

  var ICONS = {
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    mountain: '<path d="M3 19l6-10 4 6 2-3 6 7z"/>',
    palette: '<path d="M12 3a9 9 0 1 0 0 18c1.6 0 2-1.1 1.5-2.1s0-2.1 1.5-2.1h2a3 3 0 0 0 3-3C20 8 16.5 3 12 3z"/><circle cx="8" cy="11" r="1"/><circle cx="12" cy="7.5" r="1"/><circle cx="16" cy="10" r="1"/>',
    desk: '<path d="M4 6h16v9H4zM2 19h20"/>',
    people: '<circle cx="9" cy="9" r="3"/><circle cx="17" cy="10" r="2.5"/><path d="M3 19c0-3 3-5 6-5s6 2 6 5M15 14.5c3 0 6 1.5 6 4.5"/>',
    cup: '<path d="M5 8h11v6a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5zM16 10h2a2 2 0 0 1 0 4h-2M8 3v2M12 3v2"/>',
    alert: '<path d="M12 4l9 16H3zM12 10v4M12 17v.5"/>',
    compass: '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/>',
    drop: '<path d="M12 3c4 5 6 8 6 11a6 6 0 0 1-12 0c0-3 2-6 6-11z"/>',
    quote: '<path d="M7 17c-2 0-3-1.5-3-3.5C4 10 6 8 8 7M16 17c-2 0-3-1.5-3-3.5 0-3.5 2-5.5 4-6.5"/>'
  };

  var PLANTS = {
    A: { name: 'Xương rồng', latin: 'Cactaceae', tag: 'Mạnh mẽ trong im lặng',
      desc: 'Xương rồng là loài cây của những người sống tự lập và không cần phô trương. Phần lớn lựa chọn của bạn cho thấy bạn thích tự giải quyết vấn đề, giữ cuộc sống gọn gàng và chỉ giữ lại những gì thật sự cần. Giống xương rồng, bạn chịu được những giai đoạn khô hạn mà không than phiền, và khi đến lúc, bạn nở hoa rất đẹp, chỉ là không ồn ào.',
      traits: ['Bạn coi trọng sự độc lập và tự quyết định cách mình sống.', 'Bạn thích sự tối giản: ít đồ, ít lời, nhiều hiệu quả.', 'Bạn bền bỉ trước áp lực và hiếm khi bỏ cuộc giữa chừng.'],
      care: 'Gợi ý chăm sóc: đặt nơi nhiều nắng và tưới thưa, khoảng một đến hai tuần một lần.' },
    B: { name: 'Hoa hướng dương', latin: 'Helianthus annuus', tag: 'Cứ hướng về phía mặt trời',
      desc: 'Hoa hướng dương hợp với những người mang năng lượng tích cực vào mọi nơi họ đến. Bạn thích gặp gỡ, thích kể chuyện và dễ truyền cảm hứng cho người xung quanh. Khi gặp khó khăn, bạn chọn nhìn về phía có ánh sáng trước, giống cách hoa luôn xoay theo mặt trời. Một ngày yên ắng quá lâu làm bạn hơi chán, và đó là lý do bạn luôn tìm điều mới để bắt đầu.',
      traits: ['Bạn lạc quan và lan tỏa năng lượng cho cả nhóm.', 'Bạn hào hứng với trải nghiệm mới và các cuộc gặp gỡ.', 'Bạn dễ kết nối, nói chuyện tự nhiên với nhiều kiểu người.'],
      care: 'Gợi ý chăm sóc: cần nắng đầy đủ, đất luôn hơi ẩm và một chỗ trồng thoáng rộng.' },
    C: { name: 'Lan hồ điệp', latin: 'Phalaenopsis', tag: 'Đẹp nằm ở từng chi tiết',
      desc: 'Lan hồ điệp đại diện cho sự tinh tế và tỉ mỉ. Các lựa chọn của bạn cho thấy bạn thích mọi thứ ngăn nắp, làm việc có kế hoạch và để ý những chi tiết người khác bỏ qua. Bạn đặt tiêu chuẩn cao cho chính mình, và chính điều đó khiến kết quả của bạn luôn đáng tin. Giống lan, bạn tỏa sáng nhất khi có môi trường phù hợp và đủ thời gian chuẩn bị.',
      traits: ['Bạn chú ý chi tiết và muốn mọi việc được hoàn thành chỉn chu.', 'Bạn thích kế hoạch rõ ràng và nhịp làm việc đều đặn.', 'Bạn tinh tế trong thẩm mỹ và cách giao tiếp.'],
      care: 'Gợi ý chăm sóc: ánh sáng gián tiếp, tưới khi rễ chuyển sang màu bạc và tránh để nước đọng ở gốc.' },
    D: { name: 'Bonsai tùng', latin: 'Pinus bonsai', tag: 'Chậm mà chắc, càng lâu càng vững',
      desc: 'Bonsai là loài cây của sự kiên nhẫn. Bạn chọn bình tĩnh thay vì vội vã, thích lắng nghe trước khi nói và tin rằng điều tốt cần thời gian. Mỗi ngày bạn làm một chút, đều đặn, và sau nhiều năm kết quả khiến người khác ngạc nhiên. Bạn là người mà bạn bè tìm đến khi cần một lời khuyên điềm tĩnh.',
      traits: ['Bạn kiên nhẫn và đủ bình tĩnh để làm việc lâu dài.', 'Bạn là người lắng nghe, hay được nhờ tư vấn.', 'Bạn tìm sự cân bằng và thích không gian yên tĩnh.'],
      care: 'Gợi ý chăm sóc: tưới đều tay, cắt tỉa nhẹ định kỳ và đặt nơi có ánh sáng dịu.' }
  };
  var LETTERS = ['A', 'B', 'C', 'D'];

  /* ---------- Hình minh họa cây (SVG) ---------- */
  function svg(inner, w) {
    return '<svg class="plant" viewBox="0 0 200 230" width="' + w + '" aria-hidden="true" focusable="false">' + inner + '</svg>';
  }
  var POT = '<path d="M64 176h72l-7 38a8 8 0 0 1-8 6H79a8 8 0 0 1-8-6z" fill="var(--p-pot)"/>' +
    '<rect x="58" y="168" width="84" height="13" rx="5" fill="var(--p-pot)"/>' +
    '<rect x="58" y="168" width="84" height="5" rx="3" fill="#000" opacity=".1"/>';

  function cactus(w) {
    var s = '';
    s += '<path d="M84 132H68a8 8 0 0 1-8-8V102" stroke="var(--p-leaf)" stroke-width="16" stroke-linecap="round" fill="none"/>';
    s += '<path d="M116 118h16a8 8 0 0 0 8-8V90" stroke="var(--p-leaf)" stroke-width="16" stroke-linecap="round" fill="none"/>';
    s += '<rect x="82" y="74" width="36" height="110" rx="18" fill="var(--p-leaf)"/>';
    s += '<path d="M92 84v90M100 78v96M108 84v90" stroke="var(--p-leaf-d)" stroke-width="2" opacity=".45" fill="none"/>';
    s += '<g stroke="var(--p-petal)" stroke-width="1.6" stroke-linecap="round" opacity=".9"><path d="M94 100l-4-2M106 112l4-2M94 130l-4-2M106 150l4-2M100 90v-3"/></g>';
    var pet = '';
    for (var i = 0; i < 6; i++) { pet += '<ellipse cx="100" cy="62" rx="4.5" ry="8" fill="var(--p-pink)" transform="rotate(' + (i * 60) + ' 100 70)"/>'; }
    s += pet + '<circle cx="100" cy="70" r="4" fill="var(--p-sun)"/>';
    return svg(s + POT, w);
  }
  function sunflower(w) {
    var s = '<rect x="97" y="82" width="6" height="94" rx="3" fill="var(--p-leaf-d)"/>';
    s += '<path d="M100 144C70 144 58 126 56 116c28-2 42 10 44 28z" fill="var(--p-leaf)"/>';
    s += '<path d="M100 126c30 0 42-18 44-28-28-2-42 10-44 28z" fill="var(--p-leaf-d)"/>';
    for (var i = 0; i < 14; i++) { s += '<ellipse cx="100" cy="36" rx="7.5" ry="17" fill="var(--p-sun)" transform="rotate(' + (i * 360 / 14) + ' 100 64)"/>'; }
    for (var j = 0; j < 14; j++) { s += '<ellipse cx="100" cy="42" rx="6" ry="13" fill="var(--p-sun)" opacity=".8" transform="rotate(' + (j * 360 / 14 + 12) + ' 100 64)"/>'; }
    s += '<circle cx="100" cy="64" r="19" fill="var(--p-brown)"/>';
    s += '<g fill="var(--p-sun)" opacity=".55"><circle cx="94" cy="58" r="1.6"/><circle cx="104" cy="56" r="1.6"/><circle cx="108" cy="66" r="1.6"/><circle cx="98" cy="70" r="1.6"/><circle cx="90" cy="67" r="1.6"/><circle cx="100" cy="63" r="1.6"/></g>';
    return svg(s + POT, w);
  }
  function orchidFlower(x, y, k) {
    var p = '';
    for (var i = 0; i < 5; i++) { p += '<ellipse cx="0" cy="-11" rx="9" ry="13" fill="var(--p-petal)" stroke="var(--p-petal2)" stroke-width="1" transform="rotate(' + (i * 72) + ')"/>'; }
    return '<g transform="translate(' + x + ' ' + y + ') scale(' + k + ')">' + p +
      '<ellipse cx="0" cy="3" rx="5" ry="6.5" fill="var(--p-petal2)"/><circle cx="0" cy="-2" r="2.5" fill="var(--p-sun)"/></g>';
  }
  function orchid(w) {
    var s = '<ellipse cx="68" cy="164" rx="36" ry="10" transform="rotate(-14 68 164)" fill="var(--p-leaf)"/>';
    s += '<ellipse cx="134" cy="166" rx="36" ry="10" transform="rotate(12 134 166)" fill="var(--p-leaf-d)"/>';
    s += '<path d="M100 176C96 130 104 84 138 46" stroke="var(--p-leaf-d)" stroke-width="4" stroke-linecap="round" fill="none"/>';
    s += '<circle cx="146" cy="38" r="4" fill="var(--p-petal2)"/><circle cx="152" cy="32" r="2.6" fill="var(--p-petal2)"/>';
    s += orchidFlower(128, 56, .82) + orchidFlower(108, 92, .95) + orchidFlower(94, 128, 1);
    return svg(s + POT, w);
  }
  function bonsai(w) {
    var s = '<path d="M100 190C96 165 112 150 100 130C92 118 78 112 74 98" stroke="var(--p-brown)" stroke-width="10" stroke-linecap="round" fill="none"/>';
    s += '<path d="M104 148C122 144 134 132 142 114" stroke="var(--p-brown)" stroke-width="6" stroke-linecap="round" fill="none"/>';
    s += '<path d="M98 126C92 108 98 92 100 80" stroke="var(--p-brown)" stroke-width="6" stroke-linecap="round" fill="none"/>';
    s += '<ellipse cx="72" cy="92" rx="36" ry="20" fill="var(--p-leaf-d)"/><ellipse cx="140" cy="106" rx="32" ry="18" fill="var(--p-leaf-d)"/><ellipse cx="102" cy="66" rx="38" ry="22" fill="var(--p-leaf-d)"/>';
    s += '<ellipse cx="68" cy="86" rx="26" ry="12" fill="var(--p-leaf)"/><ellipse cx="136" cy="100" rx="22" ry="10" fill="var(--p-leaf)"/><ellipse cx="98" cy="60" rx="28" ry="13" fill="var(--p-leaf)"/>';
    s += '<ellipse cx="92" cy="54" rx="14" ry="5" fill="var(--p-leaf-l)" opacity=".7"/>';
    s += '<rect x="52" y="188" width="96" height="22" rx="5" fill="var(--p-pot)"/><rect x="66" y="208" width="14" height="9" fill="var(--p-pot)"/><rect x="120" y="208" width="14" height="9" fill="var(--p-pot)"/>';
    s += '<rect x="56" y="186" width="88" height="6" rx="3" fill="var(--p-soil)"/>';
    return svg(s, w);
  }
  var DRAW = { A: cactus, B: sunflower, C: orchid, D: bonsai };

  function icon(name) {
    return '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[name] + '</svg>';
  }

  /* ---------- Trạng thái ---------- */
  var N = QUESTIONS.length, idx = 0, answers = [], locked = false, userName = '';

  function showScreen($el) {
    var $cur = $('.screen:visible');
    $('html, body').animate({ scrollTop: 0 }, 200);
    if (!$cur.length) { $el.fadeIn(380); return; }
    $cur.fadeOut(220, function () { $el.fadeIn(380); });
  }

  function setProgress(i) {
    $('#fill').stop(true).animate({ width: (i / N * 100) + '%' }, 350);
  }

  function fillQuestion(i) {
    var q = QUESTIONS[i], html = '';
    $('#qnum').text('Câu ' + (i + 1) + ' / ' + N);
    $('#qicon').html(icon(q.i));
    $('#qtext').text(q.q);
    $.each(q.o, function (k, t) {
      var L = LETTERS[k];
      html += '<button type="button" class="opt' + (answers[i] === L ? ' picked' : '') + '" data-k="' + L + '"><span class="badge">' + L + '</span><span class="otext">' + t + '</span></button>';
    });
    $('#opts').html(html);
    $('#back').prop('disabled', i === 0);
    setProgress(i);
  }

  function slideTo(i) {
    $('#qbody').stop(true).animate({ opacity: 0, left: -30 }, 170, function () {
      fillQuestion(i);
      $(this).css('left', 30).animate({ opacity: 1, left: 0 }, 260, function () { locked = false; });
    });
  }

  function burst($btn, e) {
    var off = $btn.offset();
    var x = e && e.pageX ? e.pageX - off.left : $btn.outerWidth() / 2;
    var y = e && e.pageY ? e.pageY - off.top : $btn.outerHeight() / 2;
    for (var i = 0; i < 8; i++) {
      var ang = Math.random() * Math.PI * 2, d = 30 + Math.random() * 50;
      $('<span class="pt"></span>')
        .css({ left: x, top: y, transform: 'rotate(' + Math.round(Math.random() * 180) + 'deg)' })
        .appendTo($btn)
        .animate({ left: x + Math.cos(ang) * d, top: y + Math.sin(ang) * d, opacity: 0 }, 540, function () { $(this).remove(); });
    }
  }

  function choose(L, $btn, e) {
    if (locked) { return; }
    locked = true;
    answers[idx] = L;
    $btn.addClass('picked');
    burst($btn, e);
    setProgress(idx + 1);
    setTimeout(function () {
      if (idx < N - 1) { idx++; slideTo(idx); } else { finish(); }
    }, 480);
  }

  function countUp($el, pct, delay) {
    setTimeout(function () {
      $({ n: 0 }).animate({ n: pct }, { duration: 750, step: function (n) { $el.text(Math.round(n) + '%'); }, complete: function () { $el.text(Math.round(pct) + '%'); } });
    }, delay);
  }

  function finish() {
    var counts = { A: 0, B: 0, C: 0, D: 0 }, max = 0, win = 'A', i;
    $.each(answers, function (_, L) { counts[L]++; });
    $.each(counts, function (_, c) { if (c > max) { max = c; } });
    for (i = answers.length - 1; i >= 0; i--) { if (counts[answers[i]] === max) { win = answers[i]; break; } }
    var P = PLANTS[win];

    $('#r-hello').text(userName ? userName + ', loài cây hợp với bạn nhất là' : 'Loài cây phù hợp nhất với bạn');
    $('#r-name').text(P.name);
    $('#r-latin').text(P.latin);
    $('#r-tag').text('“' + P.tag + '”');
    $('#r-plant').html(DRAW[win](210));
    $('#r-desc').text(P.desc);
    $('#r-traits').html($.map(P.traits, function (t) { return '<li>' + t + '</li>'; }).join(''));
    $('#r-care').text(P.care);
    $('#r-top').html('Đáp án bạn chọn nhiều nhất là <strong>' + win + '</strong> (' + counts[win] + '/' + N + ' câu), nên kết quả của bạn là <strong>' + P.name + '</strong>.');

    var bars = '';
    $.each(LETTERS, function (_, L) {
      var pct = counts[L] / N * 100;
      bars += '<div class="bar' + (L === win ? ' win' : '') + '"><span class="lbl"><b>' + L + '</b>' + PLANTS[L].name + '</span>' +
        '<span class="tr"><span class="bar-fill" style="display:block" data-pct="' + pct + '"></span></span><span class="pc">0%</span></div>';
    });
    $('#bars').html(bars);

    var rest = $.grep(LETTERS, function (L) { return L !== win && counts[L] > 0; }).sort(function (a, b) { return counts[b] - counts[a]; });
    if (rest.length) {
      $('#r-second').text('Loài cây gần với bạn thứ hai: ' + PLANTS[rest[0]].name + ' (' + counts[rest[0]] + '/' + N + ' câu).').show();
    } else { $('#r-second').hide(); }

    showScreen($('#screen-result'));
    setTimeout(function () {
      $('#bars .bar').each(function (k) {
        var $f = $(this).find('.bar-fill'), pct = parseFloat($f.attr('data-pct'));
        $f.css('width', 0).delay(k * 130).animate({ width: pct + '%' }, 750);
        countUp($(this).find('.pc'), pct, k * 130);
      });
    }, 500);
    locked = false;
  }

  function startQuiz() {
    userName = $.trim($('#name').val()).slice(0, 24);
    idx = 0; answers = []; locked = false;
    $('#fill').stop(true).css('width', 0);
    fillQuestion(0);
    $('#qbody').css({ opacity: 1, left: 0 });
    showScreen($('#screen-quiz'));
  }

  /* ---------- Khởi tạo ---------- */
  $(function () {
    // xem trước 4 loài cây
    var pv = '';
    $.each(LETTERS, function (_, L) { pv += '<figure>' + DRAW[L](110) + '<figcaption>' + PLANTS[L].name + '</figcaption></figure>'; });
    $('#preview').html(pv);

    // bụi vàng trang trí
    var sp = '';
    for (var i = 0; i < 18; i++) {
      var s = 3 + Math.random() * 5;
      sp += '<span class="speck" style="left:' + (Math.random() * 100).toFixed(1) + '%;top:' + (Math.random() * 100).toFixed(1) + '%;width:' + s.toFixed(1) + 'px;height:' + s.toFixed(1) + 'px;animation-delay:-' + (Math.random() * 9).toFixed(1) + 's"></span>';
    }
    $('.deco').append(sp);

    $('#btn-start').on('click', startQuiz);
    $('#name').on('keydown', function (e) { if (e.key === 'Enter') { startQuiz(); } });
    $('#btn-again').on('click', startQuiz);

    $('#opts').on('click', '.opt', function (e) { choose($(this).attr('data-k'), $(this), e); });

    $('#back').on('click', function () {
      if (locked || idx === 0) { return; }
      locked = true; idx--; slideTo(idx);
    });

    $(document).on('keydown', function (e) {
      if (!$('#screen-quiz').is(':visible') || locked || e.ctrlKey || e.metaKey || e.altKey) { return; }
      var k = (e.key || '').toUpperCase();
      if (k.length === 1 && 'ABCD'.indexOf(k) > -1) { $('.opt[data-k="' + k + '"]').trigger('click'); }
    });
  });
})(jQuery);
