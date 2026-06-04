const WORKBENCH_TASK_TEMPLATES = {
  inq: {
    name: "INQ前期支持",
    note: "方案、风险、报价前输入",
    items: [
      { title: "澄清客户需求", work_package: "前期方案", phase_code: "clarification", offset_days: 2, requires_deliverable: false },
      { title: "输出大致方案", work_package: "前期方案", phase_code: "rough_solution", offset_days: 3, requires_deliverable: true },
      { title: "评估技术风险", work_package: "前期方案", phase_code: "rough_solution", offset_days: 3, requires_deliverable: false },
      { title: "提供内部报价输入", work_package: "报价支持", phase_code: "quote_support", offset_days: 4, requires_deliverable: true },
      { title: "确认客户报价资料", work_package: "报价支持", phase_code: "quote_support", offset_days: 5, requires_deliverable: true },
    ],
  },
  wo: {
    name: "WO执行",
    note: "设计、BOM、采购、装配、调试",
    items: [
      { title: "细化方案确认", work_package: "项目管理", phase_code: "wo_kickoff", offset_days: 2, requires_deliverable: true },
      { title: "机械设计", work_package: "机械设计", phase_code: "detailed_design", offset_days: 7, requires_deliverable: true },
      { title: "电气设计", work_package: "电气设计", phase_code: "detailed_design", offset_days: 7, requires_deliverable: true },
      { title: "BOM输出与确认", work_package: "BOM/采购", phase_code: "bom_purchase", offset_days: 10, requires_deliverable: true },
      { title: "采购/来料跟进", work_package: "BOM/采购", phase_code: "bom_purchase", offset_days: 14, requires_deliverable: false },
      { title: "装配", work_package: "装配", phase_code: "assembly", offset_days: 18, requires_deliverable: false },
      { title: "接线", work_package: "接线", phase_code: "wiring_debug", offset_days: 20, requires_deliverable: false },
      { title: "调试", work_package: "调试", phase_code: "wiring_debug", offset_days: 23, requires_deliverable: true },
      { title: "验收资料", work_package: "验收", phase_code: "acceptance_delivery", offset_days: 26, requires_deliverable: true },
      { title: "发货资料", work_package: "发货", phase_code: "acceptance_delivery", offset_days: 28, requires_deliverable: true },
      { title: "项目关闭归档", work_package: "关闭归档", phase_code: "closed", offset_days: 30, requires_deliverable: false },
    ],
  },
};
