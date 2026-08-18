// 单页欢迎 PPT：欢迎来到 OpenFox 的世界
// 视觉：深色夜空背景 + 星球轨道母题（大椭圆 + 小行星点缀）
const pptxgen = require('pptxgenjs');
const pres = new pptxgen();

pres.layout = 'LAYOUT_16x9'; // 10" x 5.625"
pres.author = 'OpenFox';
pres.title = '欢迎来到OpenFox的世界';

const slide = pres.addSlide();
slide.background = { color: '141A33' }; // 深靛蓝夜空

// —— 视觉母题：行星/轨道 ——
// 左上：大颗淡青行星（半透明）
slide.addShape('ellipse', {
  x: -1.6, y: -1.9, w: 3.6, h: 3.6,
  fill: { color: '1C7293', transparency: 55 },
  line: { type: 'none' },
});
// 右下：金色行星（半透明）
slide.addShape('ellipse', {
  x: 8.5, y: 3.6, w: 3.0, h: 3.0,
  fill: { color: 'F2C14E', transparency: 60 },
  line: { type: 'none' },
});
// 轨道环：细描边大圆环（星球轨道，不填充）
slide.addShape('ellipse', {
  x: 1.1, y: -1.9, w: 7.8, h: 7.8,
  fill: { type: 'none' },
  line: { color: 'CADCFC', width: 0.75, transparency: 55 },
});
// 小行星点缀（右上）
slide.addShape('ellipse', {
  x: 8.95, y: 0.55, w: 0.16, h: 0.16,
  fill: { color: 'F2C14E' },
  line: { type: 'none' },
});
slide.addShape('ellipse', {
  x: 0.9, y: 0.42, w: 0.12, h: 0.12,
  fill: { color: 'CADCFC' },
  line: { type: 'none' },
});
slide.addShape('ellipse', {
  x: 7.35, y: 5.05, w: 0.13, h: 0.13,
  fill: { color: '1C7293' },
  line: { type: 'none' },
});

// —— 主标题 ——
slide.addText(
  [
    { text: '欢迎来到 ', options: { color: 'FFFFFF', fontFace: '微软雅黑', fontSize: 40, bold: true, charSpacing: 1 } },
    { text: 'OpenFox', options: { color: 'F2C14E', fontFace: 'Arial', fontSize: 46, bold: true, charSpacing: 2 } },
    { text: ' 的世界', options: { color: 'FFFFFF', fontFace: '微软雅黑', fontSize: 40, bold: true, charSpacing: 1 } },
  ],
  {
    x: 0.75, y: 2.0, w: 8.5, h: 1.5,
    align: 'center', valign: 'middle',
    margin: 0,
  }
);

// 备注（供演示者使用）
slide.addNotes('欢迎来到 OpenFox 的世界——自研 Agent Skills 框架。');

const OUT = 'C:/Users/86138/Desktop/open_fox/workspace/OpenFox_welcome.pptx';
pres.writeFile({ fileName: OUT }).then(() => console.log('written:', OUT)).catch((e) => { console.error(e); process.exit(1); });
