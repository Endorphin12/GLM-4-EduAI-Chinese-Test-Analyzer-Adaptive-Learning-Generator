from flask import Flask, render_template, request
from zhipuai import ZhipuAI
import os
import re  # 新增导入
from dotenv import load_dotenv

load_dotenv('.env')
client = ZhipuAI(api_key=os.getenv("ZHIPU_API_KEY"))

app = Flask(__name__)

MODULE_CONFIG = {
    'total': {'full': 150, 'name': '总分'},
    'basic': {'full': 20, 'name': '基础知识'},
    'modern': {'full': 30, 'name': '现代文阅读'},
    'classic': {'full': 25, 'name': '文言文阅读'},
    'poetry': {'full': 15, 'name': '古代诗歌鉴赏'},
    'language': {'full': 10, 'name': '语言运用'},
    'writing': {'full': 50, 'name': '写作'}
}

def clean_html_content(content):
    """清洗AI返回内容中的多余文字"""
    # 去除代码块标记
    content = content.replace("```html", "").replace("```", "")
    # 去除中文解释性文字
    content = re.sub(r"^(.*?)<div", "<div", content, flags=re.DOTALL)
    # 去除尾部多余文字
    content = re.sub(r"<\/body>.*<\/html>.*", "</body></html>", content, flags=re.DOTALL)
    return content.strip()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = {k: request.form[k] for k in request.form}
        analysis_report = generate_analysis(data)
        study_plan = generate_plan(analysis_report, data['daily_time'], data)
        
        if not analysis_report or not study_plan:
            raise ValueError("AI分析结果为空，请检查API响应")
            
        return render_template('report.html', 
                             analysis=analysis_report,
                             plan=study_plan)
    except Exception as e:
        return f"系统错误：{str(e)}", 500

def generate_analysis(data):
    modules_html = "\n".join([
        f"- {MODULE_CONFIG[k]['name']}得分：{v}/{MODULE_CONFIG[k]['full']}（得分率：{int(int(v)/MODULE_CONFIG[k]['full']*100)}%）"
        for k, v in data.items() if k in MODULE_CONFIG
    ])
    
    response = client.chat.completions.create(
        model="glm-4",
        messages=[
            {"role": "system", "content": f"""请生成包含以下结构的HTML代码：
<div class="col-md-6 analysis-item" data-rate="{{得分率百分比}}">
    <p class="h5 text-neon-cyan"><i class="bi-[图标] me-2"></i>[模块名称]</p>  <!-- 增加text-neon-cyan类 -->
    <div class="progress my-3">
        <div class="progress-bar" style="width: {{得分率}}%" data-rate="{{得分率}}%"></div>
    </div>
    <small class="text-neon-cyan d-block">推荐练习：[具体练习]</small>
    <small class="text-muted">主要问题：[核心问题]</small>
</div>

按照以下规则生成：
1. 总分模块使用col-md-12，其他模块使用col-md-6
2. data-rate属性存储百分比数值（不带%）
3. 图标参考：
   - 总分：bi-trophy
   - 基础知识：bi-journal-text
   - 现代文阅读：bi-book
   - 文言文阅读：bi-file-text
   - 古代诗歌：bi-pen
   - 语言运用：bi-chat-quote
   - 写作：bi-pencil
4. 核心问题从用户输入的失分点中提取关键词
5.请严格只返回HTML代码，不要包含任何说明性文字、Markdown标记或自然语言解释，结尾以'</div>'结尾，再次强调，不允许出现任何说明性文字
6. 推荐练习需要具体到训练类型"""},  # 此处保持你的原有参数
            {"role": "user", "content": f"得分数据：{modules_html}\n失分点：{data['weakness']}"}
        ],
        temperature=0.3,
        max_tokens=8000
    )
    
    if not response.choices:
        raise RuntimeError("API未返回有效响应")
    
    raw_content = response.choices[0].message.content
    return clean_html_content(raw_content)

def generate_plan(analysis, time, data):
    response = client.chat.completions.create(
        model="glm-4",
        messages=[
            {"role": "system", "content": """你是一个资深的高中语文教师，精通各种高考常考题型和考察重点，请根据用户给出的失分点和每日学习时间上限，智能规划3日的学习任务，请生成只含有HTML结构的3日学习计划，不要返回除了html结构以外的信息：
1. 每天用<div class='mb-5 position-relative'>包裹,注意：必须使用text-neon-cyan类设置标题颜色并设置一个好看的背景
2. 每天包含：
   - 时间节点：<span class='timeline-node'>Day X</span>
   - 包含2-3个学习任务卡片
3. 每个任务卡片结构：
   <div class='plan-card'>
     <div class='plan-card-header text-neon-cyan'>【题型】任务名称</div>
     <ul class='list-group list-group-flush'>
       <li class='list-group-item'>训练内容</li>
     </ul>
   </div>

5. 每个任务卡片必须包含具体训练步骤"""},
            {"role": "user", "content": f"失分点：{data['weakness']}，每日总时长：{time}分钟，需包含文言文、现代文、作文的专项训练"}
        ],
        temperature=0.5,
        max_tokens=8000
    )
    
    if not response.choices:
        raise RuntimeError("API未返回有效响应")
    
    raw_content = response.choices[0].message.content
    return clean_html_content(raw_content)

if __name__ == '__main__':
    app.run(debug=True)