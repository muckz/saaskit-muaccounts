import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.mail import mail_managers
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.views.generic.simple import direct_to_template
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from muaccounts.models import MUAccount

try:
    import sso
except ImportError:
    USE_SSO = False
else:
    USE_SSO = getattr(settings, 'MUACCOUNTS_USE_SSO', True)


def redirect_to_muaccount(mua):
    url = mua.get_absolute_url('muaccounts_manage_general')
    if USE_SSO:
        return HttpResponseRedirect(reverse('sso')+'?next='+url)
    else:
        return HttpResponseRedirect(url)

@login_required
def claim_account(request):
    mua = request.muaccount
    if mua.owner is not None or request.method <> 'POST':
        return HttpResponseForbidden()

    context = {
        'user': request.user,
        'muaccount': request.muaccount,
        'site': Site.objects.get_current(),
        }

    subject = render_to_string('muaccounts/claim_account_subject.txt', context)
    subject = ''.join(subject.splitlines()) # must not contain newlines
    message = render_to_string('muaccounts/claim_account_email.txt', context)
    mail_managers(subject, message)

    return direct_to_template(request, 'muaccounts/claim_sent.html')

@login_required
def create_account(request):
    # Don't re-create account if one exists.
    try: mua = request.user.muaccount
    except MUAccount.DoesNotExist: pass
    else: return redirect_to_muaccount(mua)

    if request.method == 'POST':
        form = MUAccountCreateForm(request.POST)
        mua = form.get_instance(request.user)
        if mua:
            return redirect_to_muaccount(mua)
    else:
        # suggest a free subdomain name based on username.
        # Domainify username: lowercase, change non-alphanumeric to
        # dash, strip leading and trailing dashes
        dn = base = re.sub(r'[^a-z0-9-]+', '-', request.user.username.lower()).strip('-')
        taken_domains = set([
            mua.domain for mua in MUAccount.objects.filter(
                domain__contains=base).all() ])
        i = 0
        while dn in taken_domains:
            i += 1
            dn = '%s-%d' % (base, i)
        form = MUAccountCreateForm({'subdomain':dn, 'name':request.user.username})
    return direct_to_template(request, 'muaccounts/create_account.html', {'form':form})
@login_required
def remove_member(request, user_id):
    if request.method <> 'POST': return HttpResponseForbidden()
    # We edit current user's MUAccount
    account = get_object_or_404(MUAccount, owner=request.user)

    # but if we're inside a MUAccount, we only allow editing that muaccount.
    if getattr(request, 'muaccount', account) <> account:
        return HttpResponseForbidden()

    user = get_object_or_404(User, id=user_id)
    if user in account.members.all():
        account.remove_member(user)

    return HttpResponseRedirect(reverse('muaccounts_manage_general'))
