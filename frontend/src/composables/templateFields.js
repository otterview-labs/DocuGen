// Unknown fields stay multiline. A long or multiline saved value is never coerced
// into a short field or native date input, including non-ISO legacy dates.
const shortNames =
  /^(项目名称|方案名称|文档标题|标题|编制单位|建设单位|交付单位|服务单位|负责人|技术负责人|服务负责人|姓名|姓名或称呼|团队或项目|汇报人|报告周期|服务周期|会议主题|会议地点|参会人员|主持人|记录人|编制日期|版本日期|验收日期|提交日期|日期|公司名称|客户名称|联系人|联系方式|报价编号|报价日期|有效期|投标人|招标人|招标编号|岗位名称|收件人|发件人|发函日期)$/;
export function templateFieldKind(variable, value = "") {
  const text = String(value ?? "");
  if (text.includes("\n") || text.length > 120) return "long";
  if (
    /日期$/.test(variable.name) &&
    (!text || /^\d{4}-\d{2}-\d{2}$/.test(text))
  )
    return "date";
  return shortNames.test(variable.name) ? "short" : "long";
}
