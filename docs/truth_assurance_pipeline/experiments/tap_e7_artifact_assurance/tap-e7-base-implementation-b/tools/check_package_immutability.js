'use strict';
const {execSync}=require('child_process');
const pkg=process.argv[2];
const h=execSync(`cd ${pkg} && find . -type f | sort | xargs sha256sum | sha256sum`).toString().trim().split(' ')[0];
console.log('package composite hash:',h);
