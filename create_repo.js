#!/usr/bin/env node
/**
 * 创建 GitHub 仓库并推送 - 小爪子出品 🐾
 */

const https = require('https');
const { execSync } = require('child_process');
const path = require('path');

// 从环境变量获取 token，避免硬编码泄露
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || '';

if (!GITHUB_TOKEN) {
    console.error('❌ 请设置环境变量 GITHUB_TOKEN');
    console.error('   用法：export GITHUB_TOKEN=ghp_xxx');
    console.error('   或：GITHUB_TOKEN=ghp_xxx node create_repo.js');
    process.exit(1);
}
const REPO_NAME = 'tv-rename-tool';
const REPO_DESC = '电视剧批量重命名工具 - 支持 Alist/OpenList/百度网盘';

let githubUser = '';

function httpsRequest(method, url, data = null) {
    return new Promise((resolve, reject) => {
        const urlObj = new URL(url);
        const options = {
            hostname: urlObj.hostname,
            path: urlObj.pathname,
            method: method,
            headers: {
                'Authorization': `token ${GITHUB_TOKEN}`,
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json',
                'User-Agent': 'tv-rename-tool'
            }
        };

        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => {
                try {
                    const json = body ? JSON.parse(body) : {};
                    if (res.statusCode >= 200 && res.statusCode < 300) {
                        resolve(json);
                    } else {
                        reject(new Error(`HTTP ${res.statusCode}: ${json.message || body}`));
                    }
                } catch (e) {
                    reject(new Error(`解析失败：${e.message}`));
                }
            });
        });

        req.on('error', reject);
        
        if (data) {
            req.write(JSON.stringify(data));
        }
        req.end();
    });
}

async function getGithubUsername() {
    console.log('\n📝 获取 GitHub 用户名...');
    try {
        const data = await httpsRequest('GET', 'https://api.github.com/user');
        githubUser = data.login;
        console.log(`✅ 用户名：${githubUser}`);
        return githubUser;
    } catch (e) {
        console.error(`❌ 获取用户名失败：${e.message}`);
        return null;
    }
}

async function createRepo() {
    console.log(`\n📦 创建仓库：${REPO_NAME}`);
    try {
        const data = await httpsRequest('POST', 'https://api.github.com/user/repos', {
            name: REPO_NAME,
            description: REPO_DESC,
            private: false,
            auto_init: false
        });
        console.log(`✅ 仓库创建成功：${data.html_url}`);
        return data.clone_url;
    } catch (e) {
        if (e.message.includes('422')) {
            console.log(`⚠️  仓库已存在！`);
            return `https://github.com/${githubUser}/${REPO_NAME}.git`;
        }
        console.error(`❌ 创建仓库失败：${e.message}`);
        return null;
    }
}

function exec(cmd, desc) {
    console.log(`\n🔄 ${desc}...`);
    try {
        const output = execSync(cmd, {
            cwd: '/root/.openclaw/workspace',
            encoding: 'utf-8',
            timeout: 60000
        });
        if (output) console.log(output.trim());
        return true;
    } catch (e) {
        const stderr = e.stderr || e.message;
        if (stderr.includes('already exists') && cmd.includes('remote')) {
            console.log(`⚠️  远程仓库已存在，继续...`);
            return true;
        }
        console.error(`❌ 失败：${stderr}`);
        return false;
    }
}

function gitInitAndPush(cloneUrl) {
    const steps = [
        ['git init', '初始化 git 仓库'],
        ['git config user.name "小爪子"', '设置 git 用户名'],
        ['git config user.email "xiaozhua@local"', '设置 git 邮箱'],
        ['git add tv_rename.py config.example.json README_TV_RENAME.md send_email.py create_repo.js', '添加文件'],
        ['git commit -m "Initial commit: 电视剧批量重命名工具 🐾"', '提交文件'],
        [`git remote add origin ${cloneUrl}`, '添加远程仓库'],
        ['git branch -M main', '重命名分支为 main'],
        [`git push -u origin main`, '推送到 GitHub'],
    ];

    for (const [cmd, desc] of steps) {
        if (!exec(cmd, desc)) {
            return false;
        }
    }
    return true;
}

async function main() {
    console.log('🐾 小爪子 GitHub 推送工具');
    console.log('='.repeat(60));

    const username = await getGithubUsername();
    if (!username) {
        console.error('\n❌ 无法获取用户名，请检查 token');
        process.exit(1);
    }

    const cloneUrl = await createRepo();
    if (!cloneUrl) {
        process.exit(1);
    }

    console.log(`\n🚀 推送到 GitHub...`);
    const success = gitInitAndPush(cloneUrl);
    
    if (success) {
        const repoUrl = `https://github.com/${githubUser}/${REPO_NAME}`;
        console.log('\n' + '='.repeat(60));
        console.log('✅ 推送成功！');
        console.log(`🔗 仓库地址：${repoUrl}`);
        console.log('='.repeat(60));
    } else {
        console.log('\n❌ 推送失败');
        process.exit(1);
    }
}

main().catch(e => {
    console.error(`\n❌ 错误：${e.message}`);
    process.exit(1);
});
