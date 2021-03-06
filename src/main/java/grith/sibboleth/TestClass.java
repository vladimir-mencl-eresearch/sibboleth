package grith.sibboleth;


public class TestClass {

	public static void main(String[] args) {

		System.out.println("Loading list of institutions...");

		final IdpObject idpObj = new DummyIdpObject();
		final CredentialManager cm = new DummyCredentialManager();

		final Shibboleth shib = new Shibboleth(idpObj, cm);
		// shib.openurl("https://wiki.test.bestgrid.org/Shibboleth.sso/Login");
		shib.openurl("https://manager.test.aaf.edu.au/federationregistry/login");
		// shib.openurl("https://slcs1.arcs.org.au/SLCS/login");

		for (String idp : idpObj.getIdps()) {
			System.out.println(idp);
		}

	}

}
