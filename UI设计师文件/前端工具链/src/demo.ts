interface Control {
  id: string;
  x: number;
  y: number;
  visible: boolean;
}
function findControl(list: Control[], id: string): Control | null {
  const hit = list.filter(c => c.id === id && c.visible);
  return hit.length > 0 ? hit[0] : null;
}
const controls: Control[] = [
  { id: "btn_submit", x: 138, y: 487, visible: true },
  { id: "input_1",   x: 290, y: 132, visible: true },
];
console.log(JSON.stringify(findControl(controls, "btn_submit")));
