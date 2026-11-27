// Browser version tests. Run: node tests/web_test.js
const el=()=>({value:"",textContent:"",className:"",appendChild(){},addEventListener(){},setAttribute(){},set onclick(f){},set onchange(f){}});
const els={};globalThis.document={getElementById:id=>els[id]||(els[id]=el()),createElement:()=>el()};
globalThis.localStorage={getItem:()=>null,setItem(){}};
const html=require("fs").readFileSync(process.argv[2]||require("path").join(__dirname,"plainly-web.html"),"utf8");
(0,eval)(html.match(/<script>([\s\S]*)<\/script>/)[1]+"\n;globalThis.__t={compile,execute,autofix,EX};");
const {compile,execute,autofix,EX}=globalThis.__t;
let pass=0,fail=0;
const run=src=>{try{return execute(compile(src)).lines.join("|")}catch(e){return "ERR "+e.message}};
const t=(n,got,want)=>{if(got===want){pass++}else{fail++;console.log("FAIL",n,"\n  got :",got,"\n  want:",want)}};
for(const k in EX){const r=run(EX[k]);t("example "+k,/^ERR/.test(r)?r:"ok","ok")}
t("factorial",run(EX["Factorial"]),"10 factorial is 3628800");
t("primes",run(EX["Speed test"]),"Primes below one million 78498");
t("names with keywords",run("let end be 5\nlet from be 3\nlet the cat be 2\nsay end plus from plus the cat"),"10");
t("name matches builtin",run("let length be 4\nsay length\nsay length of a list of 1 and 2 and 3"),"4|3");
t("symbols in text",run("say the words Note: it costs (5) dollars; ok end words"),"Note: it costs (5) dollars; ok");
t("symbol outside text",run("let x be 5:").startsWith("ERR Plainly does not use the symbol"),true);
t("define named like builtin refused",run("define length of x as number giving number\ngive back x\nend define").startsWith("ERR the name"),true);
t("function without of",run("let a be a list of 1\nsay largest").includes("needs input"),true);
const fix=(src)=>{const f=autofix(src);return f.ok?run(f.text):"NOFIX "+f.notes.join(";")};
t("fix habits",fix('print "Hello"\nvar x = 5\nif x is 5\nsay "five"\nendif'),"Hello|five");
t("fix missing end",fix("for each n in a list of 1 and 2 do\nsay n"),"1|2");
t("fix typo keyword",fix("sya the words hi end words"),"hi");
t("fix plus on text",fix("let a be 5\nsay the words Total end words plus a"),"Total 5");
t("fix wrong end",fix("let n be 1\nwhile n is less than 3 do\nadd 1 to n\nend if\nsay n"),"3");
t("counter page compiles",compile(EX["Counter page"]).includes("_on("),true);
t("greeter page compiles",compile(EX["Greeter page"]).includes("_getn")||compile(EX["Greeter page"]).includes("_get("),true);
// ---- lessons and new features
const L=Object.keys(EX).filter(k=>k.startsWith("Lesson"));
t("eight lessons",L.length,8);
const want=["Hello! I am your first program.|You can say numbers too|42","Sam is 12|Next year Sam is 14",
"Great score!|Between 5 and 9.","Hip hip hooray!|Hip hip hooray!|Hip hip hooray!|Counting 1|Counting 2|Counting 3",
"I like cat|I like dog|I like fish|I like bird|I have 4 pets|cat","42|9"];
want.forEach((w,i)=>t("lesson "+(i+1),run(EX[L[i]]),w));
const click=(src,name,box)=>{const r=execute(compile(src));const d={};for(const e of r.els)if(e.n)d[e.n]={value:e.t,textContent:e.t};
 r.dom=d;Object.assign(globalThis.__dom=d,{});return r};
{const r=execute(compile(EX[L[6]]));r.dom.score={textContent:""};r.on["add one"]();r.on["add one"]();t("lesson 7 counts clicks",r.dom.score.textContent,"Clicks so far 2")}
for(const [said,reply] of [["HELLO bot","Hello! Nice to meet you."],["i need help","I can say hello and bye. Try those!"],["ok bye","Goodbye! Come back soon."],["what","I did not understand that. Try saying hello."]]){
 const r=execute(compile(EX[L[7]]));r.dom.message={value:said};r.dom.reply={textContent:""};r.on.talk();t("chatbot: "+said,r.dom.reply.textContent,reply)}
t("text ends before followed by",run("say the words Total followed by 5"),"Total 5");
t("text ends before and the words",run("let x be a list of the words a and the words b\nsay length of x"),"2");
t("contains ignores capitals",run("say the words Hello end words contains the words ELL end words"),"yes");
console.log(pass+" passed, "+fail+" failed (with lessons)");
