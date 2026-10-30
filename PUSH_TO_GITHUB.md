# How to Push to GitHub

Your code is ready and committed! Now push it to GitHub:

## Option 1: Using GitHub Website (Easiest)

1. **Go to GitHub:** https://github.com/new

2. **Create Repository:**
   - Repository name: `agentshield`
   - Description: `AgentShield v2 - Security layer for AI agents in supply chain (SAP Hackfest 2026)`
   - Make it **Public** or **Private** (your choice)
   - **DO NOT** check "Initialize with README" (you already have one)
   - Click **Create repository**

3. **Push Your Code:**
   
   Copy and paste these commands in PowerShell:

   ```powershell
   cd "C:\Users\Harshitha\OneDrive\Desktop\py projects\agentshield"
   
   # Add GitHub remote (replace YOUR_USERNAME with your GitHub username)
   git remote add origin https://github.com/u-harshitha007/agentshield.git
   
   # Push to GitHub
   git push -u origin main
   ```

   When prompted, enter your GitHub credentials.

4. **Done!** Your repo will be at: `https://github.com/u-harshitha007/agentshield`

---

## Option 2: Using GitHub CLI (If you install it)

1. **Install GitHub CLI:**
   - Download from: https://cli.github.com/
   - Or with winget: `winget install GitHub.cli`

2. **Authenticate:**
   ```powershell
   gh auth login
   ```

3. **Create and Push:**
   ```powershell
   cd "C:\Users\Harshitha\OneDrive\Desktop\py projects\agentshield"
   gh repo create agentshield --public --source=. --remote=origin --push
   ```

---

## Quick Commands (Copy-Paste After Creating Repo on GitHub)

```powershell
# Navigate to project
cd "C:\Users\Harshitha\OneDrive\Desktop\py projects\agentshield"

# Add remote (replace with your actual GitHub repo URL)
git remote add origin https://github.com/u-harshitha007/agentshield.git

# Push to GitHub
git push -u origin main
```

---

## If You Get Authentication Errors

### Use Personal Access Token (Recommended)

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo` (full control)
4. Generate token and COPY IT
5. When git asks for password, paste the token (not your GitHub password)

---

## What's Being Pushed

✅ 45 files  
✅ 5000+ lines of code  
✅ Complete Agent Service  
✅ Full documentation  
✅ Tests  
✅ Everything ready for team!

---

## After Pushing

1. **Share with team:** Send them the repo URL
2. **Add collaborators:** Settings → Collaborators (add Pavan, Chandan, Kirti, Yogesh)
3. **Protection:** Settings → Branches → Protect `main` branch

---

## Repository Description (Use This)

```
AgentShield - Security and control layer for AI agents executing supply-chain workflows. 
Built for SAP Hackfest 2026. Features autonomous AI with Ollama, policy-aware replanning, 
capability leases, and full audit trails. Prevents ₹59,20,000 in attack exposure.
```

---

## Repository Topics (Add These)

```
ai, security, supply-chain, sap, hackathon, ollama, fastapi, python, agent, llm
```

---

Need help? The commands above are ready to copy-paste!
